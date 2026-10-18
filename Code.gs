// Google Apps Script per AI Zen Feedback
// Istruzioni:
// 1. Copia questo codice in script.google.com
// 2. Crea un nuovo Google Sheet con colonne: Nome, Modello, Lamentela, Data
// 3. Pubblica come Web App
// 4. Copia l'URL e inseriscilo nel sito

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    var data = JSON.parse(e.postData.contents);
    
    // Validate required fields
    var nome = (data.nome || '').toString().trim();
    var modello = (data.modello || '').toString().trim();
    var lamentela = (data.lamentela || '').toString().trim();
    
    if (!nome || !lamentela) {
      return ContentService.createTextOutput(JSON.stringify({'success': false, 'error': 'Nome e Lamentela sono richiesti'}))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    // Sanitize input: limit lengths and strip HTML
    nome = nome.substring(0, 100);
    modello = modello.substring(0, 50);
    lamentela = lamentela.substring(0, 2000);
    var dataOra = new Date();
    
    sheet.appendRow([nome, modello, lamentela, dataOra]);
    
    return ContentService.createTextOutput(JSON.stringify({'success': true}))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({'success': false, 'error': err.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return ContentService.createTextOutput(JSON.stringify({'status': 'ok'}))
    .setMimeType(ContentService.MimeType.JSON);
}
