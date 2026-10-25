const { app } = require('electron');
require('./main.cjs').start().catch((error) => { console.error(error); app.exit(1); });
