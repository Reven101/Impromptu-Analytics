export default async function handler(req, res) {
  // Only allow POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Get API key from environment variable
  const apiKey = process.env.ANTHROPIC_API_KEY;
  
  if (!apiKey) {
    return res.status(500).json({ error: 'API key not configured' });
  }

  try {
    const { dataSummary, question } = req.body;

    if (!dataSummary || !question) {
      return res.status(400).json({ error: 'Missing dataSummary or question' });
    }

    const prompt = `Du er en ekspert dataanalytiker som hjelper norske brukere med å forstå dataene sine.

DATASETT INFORMASJON:
- Antall rader: ${dataSummary.rowCount}
- Antall kolonner: ${dataSummary.columnCount}
- Kolonner: ${dataSummary.headers.join(', ')}

NUMERISKE KOLONNER:
${dataSummary.numericColumns.map(c => `- ${c.name}: min=${c.min.toFixed(2)}, max=${c.max.toFixed(2)}, snitt=${c.avg.toFixed(2)}, antall=${c.count}`).join('\n') || 'Ingen numeriske kolonner'}

KATEGORISKE KOLONNER:
${dataSummary.categoricalColumns.map(c => `- ${c.name}: ${c.uniqueCount} unike verdier (eksempler: ${c.topValues.slice(0,5).join(', ')})`).join('\n') || 'Ingen kategoriske kolonner'}

UTVALG AV DATA (første 20 rader):
${dataSummary.sampleRows.map(row => row.join(' | ')).join('\n')}

BRUKERENS SPØRSMÅL:
${question}

Gi en grundig, innsiktsfull analyse på norsk. Strukturer svaret med:
1. Hovedfunn og mønstre
2. Statistiske observasjoner
3. Potensielle anomalier eller interessante datapunkter
4. Konkrete anbefalinger

Vær spesifikk og referer til faktiske tall fra dataene. Unngå generelle råd - fokuser på det som er unikt for dette datasettet.`;

    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 2000,
        messages: [
          { role: 'user', content: prompt }
        ]
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Anthropic API error:', errorData);
      return res.status(response.status).json({ error: 'AI analysis failed' });
    }

    const data = await response.json();
    const analysisText = data.content[0].text;

    return res.status(200).json({ analysis: analysisText });

  } catch (error) {
    console.error('Server error:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
