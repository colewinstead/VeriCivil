const { app, dialog } = require('electron');
const path = require('node:path');
app.setPath('userData', path.join(app.getPath('appData'), 'VeriCivil Superelevation'));
require('./main.cjs').start().catch(() => {
  dialog.showErrorBox('VeriCivil could not start', 'Check that the application folder is complete and your user profile is writable. Reinstall from vericivil.com/downloads if this repeats. Your saved projects have not been changed.');
  app.exit(1);
});
