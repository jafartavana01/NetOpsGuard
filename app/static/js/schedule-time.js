/* Shared schedule display. A blank zone is legacy UTC, never browser local. */
window.ScheduleTime = {
  format(value, zone) {
    if (!value) return '—';
    const date = new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + 'Z');
    if (!Number.isFinite(date.getTime())) return 'Unavailable';
    try { return date.toLocaleString(undefined, {timeZone: zone || 'UTC', timeZoneName: 'short'}) + ' · ' + (zone || 'UTC') + ' (UTC ' + date.toISOString() + ')'; }
    catch { return date.toISOString() + ' UTC (browser cannot display ' + zone + ')'; }
  },
  async choices(select, selected) {
    const requestId = String(Number(select.dataset.zoneRequest || 0) + 1);
    select.dataset.zoneRequest = requestId;
    select.dataset.zoneLoading = 'true';
    select.disabled = true;
    const option = (value, label) => new Option(label, value);
    select.replaceChildren(option('', 'Legacy UTC — preserve existing execution'));
    if (selected) select.add(option(selected, selected));
    select.value = selected || '';
    try {
      const response = await AAAPlatform.authedFetch('/api/system/timezone');
      if (!response.ok) throw Error('Timezone preferences unavailable');
      const data = await response.json();
      if (!Array.isArray(data.timezones) || !data.timezones.includes(data.timezone)) throw Error('Timezone preferences unavailable');
      if (!select.isConnected || select.dataset.zoneRequest !== requestId) return;
      const current = select.value;
      for (const zone of data.timezones) if (zone !== selected) select.add(option(zone, zone));
      // Only a new schedule adopts the current application preference.
      select.value = selected === undefined ? data.timezone : current;
    } catch {
      if (select.isConnected && select.dataset.zoneRequest === requestId) {
        select.title = 'Could not load timezone preferences. Existing timezone is preserved.';
        select.options[select.selectedIndex].textContent += ' — timezone list unavailable';
      }
    } finally {
      if (select.isConnected && select.dataset.zoneRequest === requestId) {
        select.dataset.zoneLoading = 'false';
        select.disabled = false;
      }
    }
  }
};
