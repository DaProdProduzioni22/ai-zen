// Google Apps Script per AI Zen Feedback
// Istruzioni:
// 1. Copia questo codice in script.google.com
// 2. Crea un nuovo Google Sheet con colonne: Nome, Modello, Lamentela, Data
// 3. Pubblica come Web App
// 4. Copia l'URL e inseriscilo nel sito

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  
  var data = JSON.parse(e.postData.contents);
  var nome = data.nome;
  var modello = data.modello || '';
  var lamentela = data.lamentela;
  var dataOra = new Date();
  
  sheet.appendRow([nome, modello, lamentela, dataOra]);
  
  return ContentService.createTextOutput(JSON.stringify({'success': true}))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet() {
  return ContentService.createTextOutput(JSON.stringify({'status': 'ok'}))
    .setMimeType(ContentService.MimeType.JSON);
}
