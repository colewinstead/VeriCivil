const editions = require('./editions.json');

function getEdition(id = process.env.DESKTOP_EDITION ?? 'vericivil') {
  if (!Object.hasOwn(editions, id)) throw new Error(`Unknown desktop edition: ${id}`);
  return Object.freeze({ id, ...editions[id] });
}

function updateChannel(edition, platform, arch, signed = false) {
  return `${edition.channelPrefix}${signed ? '' : 'unsigned-'}${platform}-${arch}`;
}

module.exports = { getEdition, updateChannel };
