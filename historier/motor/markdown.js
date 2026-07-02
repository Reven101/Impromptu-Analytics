/* Minimal markdown-renderer for tekst.md-filer.
   Støtter: ## overskrifter, avsnitt, **fet**, *kursiv*, [lenker](url),
   - punktlister, > sitat. Alt tekstinnhold escapes før inline-formatering,
   så innholdsfiler kan aldri injisere HTML. */

const ESCAPE = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };

export function escapeHtml(tekst) {
  return String(tekst).replace(/[&<>"]/g, (t) => ESCAPE[t]);
}

function trygUrl(url) {
  return /^(https?:\/\/|\/|\.\/|\.\.\/|#|mailto:)/.test(url) ? url : "#";
}

function inline(tekst) {
  return escapeHtml(tekst)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, t, url) =>
      `<a href="${trygUrl(url)}" rel="noopener">${t}</a>`);
}

/* Returnerer en liste av blokker: {html} for prose, {viz} for [[viz:id]]. */
export function parseTekst(md) {
  const blokker = [];
  const avsnitt = md.replace(/\r\n/g, "\n").split(/\n{2,}/);

  for (const rå of avsnitt) {
    const blokk = rå.trim();
    if (!blokk) continue;

    const vizTreff = blokk.match(/^\[\[viz:([\w-]+)\]\]$/);
    if (vizTreff) { blokker.push({ viz: vizTreff[1] }); continue; }

    if (/^##\s/.test(blokk)) {
      blokker.push({ html: `<h2>${inline(blokk.replace(/^##\s+/, ""))}</h2>` });
    } else if (/^###\s/.test(blokk)) {
      blokker.push({ html: `<h3>${inline(blokk.replace(/^###\s+/, ""))}</h3>` });
    } else if (/^>\s?/.test(blokk)) {
      const indre = blokk.split("\n").map((l) => l.replace(/^>\s?/, "")).join(" ");
      blokker.push({ html: `<blockquote>${inline(indre)}</blockquote>` });
    } else if (blokk.split("\n").every((l) => /^[-*]\s/.test(l))) {
      const punkter = blokk.split("\n")
        .map((l) => `<li>${inline(l.replace(/^[-*]\s+/, ""))}</li>`).join("");
      blokker.push({ html: `<ul>${punkter}</ul>` });
    } else {
      blokker.push({ html: `<p>${inline(blokk.replace(/\n/g, " "))}</p>` });
    }
  }
  return blokker;
}
