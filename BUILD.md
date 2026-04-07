# VOID Windows Installer Build Guide

This guide explains how to build the VOID Assistant Windows installer using electron-builder.

## Prerequisites

1. **Node.js** - Make sure Node.js is installed
2. **npm packages** - Install dependencies

## Installation

### Step 1: Install electron-builder

```bash
cd VOID
npm install electron-builder --save-dev
```

Or if already in package.json:
```bash
npm install
```

### Step 2: Build the Installer

```bash
npm run build
```

This will create the Windows NSIS installer in the `dist` folder.

## Output

After building, you'll find:

```
VOID/dist/
├── VOID Assistant Setup.exe    # Main installer
└── ...
```

## Installation Options

The installer will:

- ✅ Create Desktop shortcut
- ✅ Create Start Menu entry
- ✅ Allow custom installation directory

## Running the Installer

1. Double-click `VOID Assistant Setup.exe`
2. Follow the installation wizard
3. Choose installation location
4. Click Install
5. Launch from Desktop or Start Menu

## Development Mode

To run VOID without building:

```bash
npm start
```

or

```bash
npm run dev
```

## Troubleshooting

### Icon not showing

Make sure `desktop/assets/icon.ico.png` exists. If not, you can use any `.ico` or `.png` file.

### Build fails

- Ensure Node.js is up to date
- Try: `npm cache clean --force`
- Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`

### Installer too large

The build includes all node_modules. You can optimize by excluding unused files in the `files` section of package.json.
