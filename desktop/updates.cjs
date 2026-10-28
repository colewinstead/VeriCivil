const { EventEmitter } = require('node:events');

function availableVersion(release, currentVersion) {
  if (!release || release.draft || release.prerelease || !/^v\d+\.\d+\.\d+$/.test(release.tag_name) || !/^\d+\.\d+\.\d+$/.test(currentVersion)) throw new Error('Invalid release version.');
  const next = release.tag_name.slice(1).split('.').map(Number), current = currentVersion.split('.').map(Number);
  const difference = next.map((value, index) => value - current[index]).find(value => value !== 0) || 0;
  return difference > 0 ? release.tag_name.slice(1) : null;
}

class Updates extends EventEmitter {
  constructor(updater, { enabled, version, isDirty, closeWindows, record, discover }) {
    super();
    this.updater = updater;
    this.isDirty = isDirty;
    this.closeWindows = closeWindows;
    this.record = record;
    this.enabled = enabled;
    this.discover = discover;
    this.state = { status: enabled ? 'idle' : 'disabled', version, message: enabled ? 'Updates are checked automatically.' : 'Automatic installation requires a signed production build. Get the latest download at vericivil.com/downloads.' };
    updater.autoDownload = false;
    updater.autoInstallOnAppQuit = false;
    updater.allowPrerelease = false;
    updater.allowDowngrade = false;
    updater.disableWebInstaller = true;
    updater.logger = null;
    for (const [event, status] of [['checking-for-update', 'checking'], ['update-available', 'available'], ['update-not-available', 'current'], ['update-downloaded', 'downloaded']]) {
      updater.on(event, info => this.publish({ status, nextVersion: info?.version || '', message: '', notes: typeof info?.releaseNotes === 'string' ? info.releaseNotes.slice(0, 12000) : '' }));
    }
    updater.on('download-progress', progress => this.publish({ status: 'downloading', percent: Math.max(0, Math.min(100, Number(progress.percent) || 0)) }));
    updater.on('error', error => { record('update_failed', error.code); this.publish({ status: 'error', message: 'The update could not finish. Your current app is unchanged. Check your connection and retry.' }); });
  }
  publish(update) { this.state = { ...this.state, ...update }; this.emit('state', this.state); }
  async action(action) {
    if (!['check', 'download', 'install'].includes(action)) throw new Error('Unknown update action.');
    if (!this.enabled) {
      if (action === 'check' && this.discover && this.state.status !== 'checking') {
        this.publish({ status: 'checking', message: 'Checking for a newer desktop download…' });
        try {
          const nextVersion = await this.discover();
          this.publish({ status: nextVersion ? 'manual' : 'disabled', nextVersion: nextVersion || '', message: nextVersion ? `Version ${nextVersion} is available. This unsigned build requires a manual download.` : 'No newer desktop release was found. Automatic installation requires a signed production build.' });
        } catch { this.publish({ status: 'disabled', message: 'Could not check for updates. You can keep working offline or visit vericivil.com/downloads.' }); }
      }
      return this.state;
    }
    try {
      if (action === 'check' && !['checking', 'downloading', 'downloaded', 'installing'].includes(this.state.status)) await this.updater.checkForUpdates();
      if (action === 'download' && this.state.status === 'available') {
        this.publish({ status: 'downloading', percent: 0 });
        await this.updater.downloadUpdate();
      }
      if (action === 'install' && this.state.status === 'downloaded') {
        if (this.isDirty()) {
          this.publish({ message: 'Save your project before restarting to install the update.' });
          return this.state;
        }
        // Close through the normal unsaved-work guard before invoking the updater.
        if (!await this.closeWindows()) return this.state;
        this.publish({ status: 'installing', message: 'Restarting to install…' });
        this.updater.quitAndInstall(false, true);
      }
    } catch (error) {
      this.record('update_failed', error.code);
      this.publish({ status: 'error', message: 'The update could not finish. Your current app is unchanged. Check your connection and retry.' });
    }
    return this.state;
  }
}
module.exports = { Updates, availableVersion };
