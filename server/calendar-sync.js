// Synchronisation avec un calendrier iCloud partagé (webcal/.ics) pour en extraire les gardes.
// Ne lit que ce dont le planning a besoin (événements dont le résumé contient "garde") ;
// le reste du calendrier (vie privée, autres événements) n'est jamais exposé par l'API.

const CALENDAR_URL = process.env.CALENDAR_ICS_URL || "";

function unfold(text) {
  // RFC5545 : une ligne repliée continue sur la suivante si celle-ci commence par un espace/tab.
  return text.replace(/\r\n/g, "\n").replace(/\n[ \t]/g, "");
}

function parseDT(val) {
  // Formats possibles : "20260929T090000" (horodaté) ou "20260929" (jour entier).
  const m = /^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2}))?/.exec(val || "");
  if (!m) return null;
  const [, y, mo, d, h, mi] = m;
  return { date: `${y}-${mo}-${d}`, time: h ? `${h}:${mi}` : null };
}

function parseEvents(ics) {
  const unfolded = unfold(ics);
  const blocks = unfolded.split("BEGIN:VEVENT").slice(1);
  const events = [];
  for (const block of blocks) {
    const body = block.split("END:VEVENT")[0];
    let summary = "";
    let dtstart = null;
    let dtend = null;
    for (const raw of body.split("\n")) {
      const line = raw.trim();
      const idx = line.indexOf(":");
      if (idx === -1) continue;
      const key = line.slice(0, idx);
      const val = line.slice(idx + 1);
      const keybase = key.split(";")[0];
      if (keybase === "SUMMARY") summary = val.trim();
      else if (keybase === "DTSTART") dtstart = parseDT(val);
      else if (keybase === "DTEND") dtend = parseDT(val);
    }
    if (summary && dtstart && dtend) events.push({ summary, dtstart, dtend });
  }
  return events;
}

async function fetchGardes() {
  if (!CALENDAR_URL) {
    return { updated_at: null, gardes: [], enabled: false, error: null };
  }
  const httpsUrl = CALENDAR_URL.replace(/^webcal:\/\//i, "https://");
  const res = await fetch(httpsUrl);
  if (!res.ok) throw new Error(`calendrier injoignable (HTTP ${res.status})`);
  const ics = await res.text();
  const events = parseEvents(ics);

  const gardes = events
    .filter((e) => e.summary.toLowerCase().includes("garde"))
    .map((e) => ({
      debut_date: e.dtstart.date,
      debut_time: e.dtstart.time,
      fin_date: e.dtend.date,
      fin_time: e.dtend.time,
      // Le lendemain d'une garde (jour de récupération) = date de fin de l'événement,
      // que la garde soit horodatée ou en "jour entier" (DTEND exclusif en iCal).
      jour_recuperation: e.dtend.date,
    }))
    .sort((a, b) => a.debut_date.localeCompare(b.debut_date));

  return { updated_at: new Date().toISOString(), gardes, enabled: true, error: null };
}

module.exports = { fetchGardes, parseEvents, parseDT, CALENDAR_URL };
