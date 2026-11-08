# Документация Litebee

Здесь собрано всё, что написано по проекту: как пользоваться средой, как устроен дрон и что мы узнали из прошивок. Пометки достоверности в разборах прошивки: **ПРОЧТЕНО** (видно в файле, в памяти или в ответе устройства), **ВЫВОД** (наше заключение), **НЕИЗВЕСТНО**.

## С чего начать

| Если нужно | Читайте |
|---|---|
| Понять систему целиком, простым языком, с рисунками | [kniga/kniga.pdf](kniga/kniga.pdf) (книга об устройстве, 45 страниц, XeLaTeX) |
| Узнать, как устроены железо, службы и сеть | [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) |
| Научиться писать шоу | [uchebnik/uchebnik.pdf](uchebnik/uchebnik.pdf) (учебник) |
| Понять, как дрон находит себя по меткам | [FIRMWARE_MARKERS.md](FIRMWARE_MARKERS.md), [firmware/POSITION_MODULE_V831.md](firmware/POSITION_MODULE_V831.md) |
| Увидеть, что ещё неизвестно | [FIRMWARE_UNKNOWNS.md](FIRMWARE_UNKNOWNS.md) |

## Прошивка и устройство

| Файл | О чём |
|---|---|
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Три компьютера, службы, режимы Wi-Fi, порты, безопасность, живые опыты |
| [FIRMWARE_ARCHITECTURE.md](FIRMWARE_ARCHITECTURE.md) | Слои автопилота, потоки данных |
| [FIRMWARE_MARKERS.md](FIRMWARE_MARKERS.md) | Формула «номер метки → координаты», вопрос про ArUco |
| [FIRMWARE_UNKNOWNS.md](FIRMWARE_UNKNOWNS.md) | Что выяснено и что нет |
| [firmware/POSITION_MODULE_V831.md](firmware/POSITION_MODULE_V831.md) | Модуль с камерой (Allwinner V831): программа, кадр, команды, образ флеша |
| [firmware/MODULE_UART_LINK.md](firmware/MODULE_UART_LINK.md) | UART между модулем и автопилотом |
| [firmware/WING_DRONE_USB.md](firmware/WING_DRONE_USB.md) | Дрон Wing по USB (ADB), живые проверки |
| [firmware/BUZZER_EXTENSION.md](firmware/BUZZER_EXTENSION.md) | Зуммер на модуле: протокол, мелодия по Wi-Fi |
| [firmware/AWLINK_TABLE.md](firmware/AWLINK_TABLE.md) | Протокол awlink: все команды |
| [firmware/MISSION_AND_MODES.md](firmware/MISSION_AND_MODES.md) | Миссия и режимы полёта |
| [firmware/WING_MOBILE_APP.md](firmware/WING_MOBILE_APP.md) | Мобильное приложение Wing |
| [firmware/GO_APP_CAMERA_AND_UPDATE.md](firmware/GO_APP_CAMERA_AND_UPDATE.md) | Камера и обновление в LiteBee Go |
| [firmware/HARDWARE_WING.md](firmware/HARDWARE_WING.md) | Аппаратная часть Wing |

## Протоколы и управление

| Файл | О чём |
|---|---|
| [PROTOCOL_STEPS.md](PROTOCOL_STEPS.md) | Шаги миссии формации (Wi-Fi) |
| [PROTOCOL_SINGLE.md](PROTOCOL_SINGLE.md) | Одиночный режим, USB-пульт, полёты Wing |
| [WING_MANUAL_NOTES.md](WING_MANUAL_NOTES.md) | Заметки по инструкции, привязка пульта |

## Приложение

| Файл | О чём |
|---|---|
| [UI_DESIGN.md](UI_DESIGN.md), [DESIGN.md](DESIGN.md) | Дизайн интерфейса |
| [REFERENCES.md](REFERENCES.md) | Размеры дрона и коврика, источники |

## Книги

* `kniga/` собирается так: `cd docs/kniga && latexmk -xelatex kniga.tex` (нужны XeLaTeX и шрифты Charis SIL, Fira Sans, JetBrains Mono). Готовый PDF лежит рядом.
* `uchebnik/`: так же, `latexmk -xelatex uchebnik.tex`.

## Что в репозиторий не входит

Прошивки и приложения производителя (образы, архивы, APK, бинарные файлы) в репозиторий не добавляются, это чужие файлы. Копии лежат у владельца отдельно (папка `LiteBee_firmware_original`), список с контрольными суммами есть в её `README.md`. В документах нет паролей и ключей, найденных в прошивках.
