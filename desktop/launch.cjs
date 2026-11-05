const { app, dialog } = require('electron');
const path = require('node:path');
const edition = require('./edition.json');
app.setName(edition.productName);
app.setPath('userData', path.join(app.getPath('appData'), edition.profileDirectory));
require('./main.cjs').start().catch(() => {
  dialog.showErrorBox(`${edition.productName} could not start`, `Check that the application folder is complete and your user profile is writable. Reinstall ${edition.productName} if this repeats. Your saved projects have not been changed.`);
  app.exit(1);
});
