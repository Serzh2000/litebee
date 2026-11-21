import pkg from '../../../package.json'

/** The version shown to the person (start screen footer): read once from package.json at build time. */
export const APP_VERSION: string = pkg.version
