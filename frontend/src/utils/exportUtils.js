import { AUTH_HEADER } from './auth'

export function exportToCsv(columns, rows, filename) {
  const filteredCols = columns.filter(c => !c.startsWith('_'))
  const headers = filteredCols.join(',')
  
  const csvRows = rows.map(row => {
    return filteredCols.map(col => {
      let val = row[col]
      if (col === 'top_factors' && Array.isArray(val)) {
        val = val.map(f => `${f.factor}(${f.contribution})`).join(', ')
      }
      
      let strVal = val === null || val === undefined ? '' : String(val)
      if (strVal.includes(',') || strVal.includes('\n') || strVal.includes('"')) {
        strVal = `"${strVal.replace(/"/g, '""')}"`
      }
      return strVal
    }).join(',')
  })
  
  const csvContent = [headers, ...csvRows].join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export async function sendToWebhook(url, data) {
  const response = await fetch('/api/webhook/send', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': AUTH_HEADER,
    },
    body: JSON.stringify({
      webhook_url: url,
      payload: data,
    }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to send webhook')
  }

  return await response.json()
}
