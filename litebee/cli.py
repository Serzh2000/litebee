"""Command line: python -m litebee <listen|color|hop|simulate|import-lbg|wing-status|wing-fly>.

Every subcommand accepts --port (TCP port override, default 18001; ignored by
the offline subcommands). --udp-port overrides the drone announce port (13146).
"""
import argparse
import os
import sys
import time

from . import protocol as proto
from .flight import MissionRejected, run_mission
from .link import Link
from .loader import ShowLoadError, load_show
from .mission import (COLORS, DEFAULT_MAX_HEIGHT_CM, HARD_MAX_HEIGHT_CM, MAX_HOVER_S, MIN_TAKEOFF_CM, hop_mission,
                      resolve_max_height, rgb_mission)
from .safety import MIN_VOLTS, SafetyError, check_show

LAND_FLAG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "LAND_NOW")


def _add_net(p, drone_required=True):
    p.add_argument("--pc", required=True, help="IP этого ПК в сети дронов")
    p.add_argument("--drone", required=drone_required, action="append", default=[],
                   help="IP дрона (белый список); можно повторять")


def _add_max_height(p):
    p.add_argument("--max-height", type=int, default=DEFAULT_MAX_HEIGHT_CM, metavar="СМ",
                   help=f"лимит высоты, см (по умолчанию {DEFAULT_MAX_HEIGHT_CM}; от {MIN_TAKEOFF_CM} "
                        f"до {HARD_MAX_HEIGHT_CM}, выше нельзя)")


def build_parser():
    ap = argparse.ArgumentParser(prog="litebee", description="Litebee: дроны LiteBee Wing из Python")
    ap.add_argument("--port", type=int, default=proto.TCP_PORT, help="TCP-порт сервера (по умолчанию 18001)")
    ap.add_argument("--udp-port", type=int, default=proto.UDP_REMOTE, help="UDP-порт дронов (по умолчанию 13146)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--port", type=int, default=argparse.SUPPRESS)
    common.add_argument("--udp-port", type=int, default=argparse.SUPPRESS)

    p = sub.add_parser("listen", parents=[common], help="только слушать телеметрию, ничего не посылать дрону")
    _add_net(p, drone_required=False)
    p.add_argument("--seconds", type=float, default=30)

    p = sub.add_parser("color", parents=[common], help="зажечь светодиод (без взлёта)")
    _add_net(p)
    p.add_argument("--land-flag", default=LAND_FLAG, help="файл-флаг: если появился, дрон садится")
    p.add_argument("--color", choices=COLORS, default="green")
    p.add_argument("--hold", type=float, default=8, help="сколько секунд смотреть до остановки")

    p = sub.add_parser("hop", parents=[common], help="взлёт, зависание и посадка; без --go только загрузка")
    _add_net(p)
    p.add_argument("--height", type=int, default=100, help="см")
    p.add_argument("--hover", type=float, default=3, help="секунды")
    _add_max_height(p)
    p.add_argument("--min-volts", type=float, default=MIN_VOLTS)
    p.add_argument("--land-flag", default=LAND_FLAG, help="файл-флаг: если появился, дрон садится")
    p.add_argument("--go", action="store_true", help="реально запустить моторы")

    p = sub.add_parser("simulate", parents=[common], help="симуляция шоу (.py или .lbg) и отчёт проверок")
    p.add_argument("show")
    p.add_argument("--min-distance", type=float, default=60.0, help="порог сближения, см")
    _add_max_height(p)

    p = sub.add_parser("import-lbg", parents=[common], help="превратить проект .lbg в файл шоу на Python")
    p.add_argument("src")
    p.add_argument("dst")

    p = sub.add_parser("wing-status", parents=[common],
                       help="USB-пульт Wing: приветствие, версия, пакет данных (только чтение, дрон не двигается)")
    p.add_argument("--serial", default=None, help="COM-порт пульта (по умолчанию единственный CP210x/CH340)")
    p.add_argument("--seconds", type=float, default=5, help="сколько секунд слушать поток данных")

    p = sub.add_parser("wing-fly", parents=[common],
                       help="Wing через USB-пульт: взлёт, сдвиг вперёд и вправо, посадка; без --go только проверки")
    p.add_argument("--serial", default=None, help="COM-порт пульта (по умолчанию единственный CP210x/CH340)")
    p.add_argument("--forward", type=int, default=30, help="сдвиг вперёд, см (0 = пропустить)")
    p.add_argument("--right", type=int, default=30, help="сдвиг вправо, см (0 = пропустить)")
    p.add_argument("--height", type=int, default=80, help="высота зависания после взлёта, см (30-120)")
    p.add_argument("--speed", type=int, default=15, help="скорость сдвига, см/с (5-25): путь = скорость × время")
    p.add_argument("--min-volts", type=float, default=7.4, help="минимум батареи для старта (ниже 7.0 нельзя)")
    p.add_argument("--land-flag", default=LAND_FLAG, help="файл-флаг: если появился, дрон садится")
    p.add_argument("--go", action="store_true", help="реально запустить моторы")
    return ap


def _link(args, log):
    if args.pc.startswith("127.") and args.port in proto.REAL_PORTS:
        raise SystemExit("На loopback нельзя использовать реальные порты 18001/6000/13146; задайте --port")
    link = Link(args.pc, tcp_port=args.port, udp_remote_port=args.udp_port,
                whitelist=args.drone or None, announce_targets=args.drone, log=log)
    try:
        return link.start()
    except OSError as e:
        raise SystemExit(f"Порт {args.port} занят ({e}). Закройте LiteBee Go и повторите") from e


def cmd_listen(args):
    log = lambda m: print(f"[listen] {m}")  # noqa: E731
    link = _link(args, log)
    try:
        end, last, seen = time.time() + args.seconds, 0.0, set()
        while time.time() < end:
            for ip, dc in link.connections().items():
                t = dc.snapshot()
                if t and ip not in seen:
                    seen.add(ip)
                    print(f"[listen] сырая телеметрия {ip}: {t.raw.hex(' ')}")
                if t and time.time() - last > 1:
                    print(f"[listen] {ip}: {t.as_dict()}")
            if time.time() - last > 1:
                last = time.time()
            time.sleep(0.2)
    finally:
        link.close()
    print("[listen] готово")
    return 0


def _run(args, mission, go, hold=None):
    log = lambda m: print(f"[{args.cmd}] {m}")  # noqa: E731
    link = _link(args, log)
    try:
        ip = args.drone[0]
        log(f"Ждём дрон {ip} ...")
        link.wait_for(ip, 30)
        if os.path.exists(args.land_flag):
            os.remove(args.land_flag)
        run_mission(link, ip, mission, go=go, min_volts=getattr(args, "min_volts", MIN_VOLTS),
                    max_height_cm=getattr(args, "max_height", None), hold=hold, land_flag=args.land_flag, log=log)
    except (SafetyError, MissionRejected, TimeoutError) as e:
        print(f"[{args.cmd}] {e}")
        return 1
    finally:
        link.close()
    return 0


def cmd_color(args):
    r, g, b = COLORS[args.color]
    print(f"[color] миссия из одного RGB-шага {args.color}, ожидаемая контрольная сумма 50")
    return _run(args, rgb_mission(r, g, b), go=True, hold=args.hold)  # LED only: cannot fly


def cmd_hop(args):
    if args.min_volts < MIN_VOLTS:
        print(f"[hop] --min-volts нельзя ставить ниже {MIN_VOLTS}")
        return 1
    try:
        mission = hop_mission(args.height, args.hover, max_height_cm=args.max_height)
    except SafetyError as e:
        print(f"[hop] {e}")
        return 1
    print(f"[hop] миссия: {len(mission.steps)} шага, ~{mission.total_seconds:.0f} с, высота {args.height} см "
          f"(лимит {args.max_height} см), ожидаемая контрольная сумма {mission.checksum}")
    return _run(args, mission, go=args.go)


def cmd_simulate(args):
    try:
        limit = resolve_max_height(args.max_height)
    except SafetyError as e:
        print(f"[simulate] {e}")
        return 1
    show = load_show(args.show)
    print(show.report())
    print(f"Лимит высоты: {limit} см")
    findings = check_show(show, args.min_distance, max_height_cm=limit)
    print("Проверки безопасности:" if findings else "Проверки безопасности: замечаний нет")
    for f in findings:
        print(f"  {f}")
    return 1 if any(f.level == "error" for f in findings) else 0


def cmd_import_lbg(args):
    from .lbg import LbgError, convert
    try:
        convert(args.src, args.dst)
    except LbgError as e:
        print(e)
        return 1
    print(f"Записано {args.dst}")
    return 0


def cmd_wing_status(args):
    """Talk to the USB remote exactly like LiteBee Go does on connect; only read-only messages are written."""
    from . import remote
    try:
        link = remote.open_link(args.serial)
    except remote.RemoteError as e:
        print(f"[wing] {e}")
        return 1
    with link:
        if not link.handshake():
            print("[wing] пульт не ответил на приветствие. Закройте LiteBee Go и проверьте кабель")
            return 1
        print("[wing] пульт ответил на приветствие")
        v = link.request_version()
        if v:
            print(f"[wing] версии: пульт {v.rv_text}, дрон {v.fv_text or 'неизвестна (дрон не связан с пультом)'}")
        else:
            print("[wing] версию пульт не прислал")
        link.request_data()
        link.run(args.seconds)
        if link.last_data is None:
            print("[wing] пакетов данных нет")
            return 1
        print(f"[wing] пакетов данных за {args.seconds:g} с: {link.data_count}; последний: {link.last_data.raw.hex(' ')}")
        if link.last_data.is_empty:
            print("[wing] пакет нулевой: пульт на связи с компьютером, но не видит дрона")
        else:
            d = link.last_data
            x, y, z = d.pos
            print("[wing] пульт видит дрон")
            print(f"[wing] батарея {d.voltage:.1f} В; положение x={x} y={y} z={z} см; углы: крен {d.roll_deg:.1f}°, "
                  f"тангаж {d.pitch_deg:.1f}°, рыскание {d.yaw_deg:.1f}°; режим {d.mode}; скорость {d.speed}")
    return 0


def cmd_wing_fly(args):
    """One test flight of a Wing through the USB remote. Without --go nothing but read-only messages is sent."""
    import datetime
    from . import remote, wing
    log_path = os.path.join(os.path.dirname(LAND_FLAG), "flight_logs",
                            datetime.datetime.now().strftime("wing_%Y%m%d_%H%M%S.txt"))

    def log(m):
        line = f"[wing] {m}"
        print(line)
        if args.go:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    moves = ([(0, args.forward)] if args.forward else []) + ([(args.right, 0)] if args.right else [])
    try:
        wing.check_plan(moves)
        link = remote.open_link(args.serial, allow_commands=args.go)
    except (SafetyError, remote.RemoteError) as e:
        print(f"[wing] {e}")
        return 1
    with link:
        try:
            flight = wing.WingFlight(link, land_flag=args.land_flag, min_volts=args.min_volts,
                                     hover_cm=args.height, speed_cm_s=args.speed, log=log)
            plan = f"зависание на {args.height} см; " + "; ".join(f"вправо {r} см, вперёд {f} см" for r, f in moves)
            if not args.go:
                flight.preflight()
                print(f"[wing] проверки пройдены. План: взлёт; {plan}; посадка. Команды НЕ отправлены (нужен --go)")
                return 0
            if os.path.exists(args.land_flag):
                os.remove(args.land_flag)
            print(f"[wing] ПОЛЁТ: калибровка, взлёт; {plan}; посадка. Остановить: Ctrl+C или файл {args.land_flag}")
            flight.fly(moves)
        except (SafetyError, wing.FlightAbort, remote.RemoteError) as e:
            print(f"[wing] {e}")
            return 1
        except KeyboardInterrupt:
            print("[wing] прервано, дрон посажен")
            return 130
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    handler = {"listen": cmd_listen, "color": cmd_color, "hop": cmd_hop, "simulate": cmd_simulate,
               "import-lbg": cmd_import_lbg, "wing-status": cmd_wing_status, "wing-fly": cmd_wing_fly}[args.cmd]
    try:
        return handler(args)
    except ShowLoadError as e:
        print(e)
        return 1
    except KeyboardInterrupt:
        print("Прервано")
        return 130
