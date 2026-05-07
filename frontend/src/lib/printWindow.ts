export class PrintWindowBlockedError extends Error {
  constructor() {
    super('Popup blocked. Allow popups for this workstation to print labels.');
    this.name = 'PrintWindowBlockedError';
  }
}

function writeDocument(win: Window, html: string) {
  win.document.open();
  win.document.write(html);
  win.document.close();
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function openBlankPrintWindow(title = 'Preparing labels'): Window {
  const win = window.open('', '_blank', 'width=800,height=900');
  if (!win) throw new PrintWindowBlockedError();

  try {
    win.opener = null;
  } catch {
    // Some browsers disallow assigning opener; the window is still usable.
  }

  writeDocument(win, `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>${escapeHtml(title)}</title>
    <style>
      :root { color-scheme: light; }
      body {
        min-height: 100vh; margin: 0; display: grid; place-items: center;
        font-family: ui-sans-serif, system-ui, sans-serif; color: #0f172a; background: #fff;
      }
      p { margin: 0; font-size: 14px; }
    </style>
  </head>
  <body>
    <p>Preparing labels...</p>
  </body>
</html>`);

  return win;
}

export function writePrintWindow(win: Window, title: string, bodyHtml: string, extraCss = '') {
  writeDocument(win, `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>${escapeHtml(title)}</title>
    <style>
      :root { color-scheme: light; }
      body { margin: 0; padding: 24px; font-family: ui-sans-serif, system-ui, sans-serif; color: #0f172a; background: #fff; }
      h1 { font-size: 14px; margin: 0 0 16px; }
      .label {
        display: flex; flex-direction: column; align-items: center; gap: 4px;
        border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; text-align: center;
      }
      .label .name { font-weight: 600; font-size: 12px; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .label .sku { font-family: ui-monospace, monospace; font-size: 10px; color: #475569; }
      .label .price { font-weight: 600; font-size: 12px; margin-top: 2px; }
      .label .err { color: #b91c1c; font-size: 10px; }
      .label img { max-width: 100%; height: auto; }
      .sheet { display: grid; grid-template-columns: repeat(3, 2.625in); grid-auto-rows: 1in; gap: 0; border: 0; }
      .sheet .label { border: 1px dashed #e2e8f0; border-radius: 0; padding: 4px; gap: 2px; }
      .sheet .label .name { font-size: 9px; }
      .sheet .label .sku { font-size: 7px; }
      .sheet .label .price { font-size: 9px; }
      @media print {
        body { padding: 0; }
        h1 { display: none; }
        .label, .sheet .label { border-color: transparent; page-break-inside: avoid; }
      }
      ${extraCss}
    </style>
  </head>
  <body>
    ${bodyHtml}
    <script>
      function printWhenReady() {
        const imagePromises = Array.from(document.images).map((img) => {
          if (img.complete) return Promise.resolve();
          return new Promise((resolve) => {
            img.addEventListener('load', resolve, { once: true });
            img.addEventListener('error', resolve, { once: true });
          });
        });
        Promise.all(imagePromises).then(() => {
          requestAnimationFrame(() => {
            setTimeout(() => {
              window.focus();
              window.print();
            }, 100);
          });
        });
      }
      if (document.readyState === 'complete') {
        printWhenReady();
      } else {
        window.addEventListener('load', printWhenReady, { once: true });
      }
    </script>
  </body>
</html>`);

  win.focus();
}

export function printWindowWhenReady(win: Window, delayMs = 100) {
  const printWhenReady = () => {
    const imagePromises = Array.from(win.document.images).map((img) => {
      if (img.complete) return Promise.resolve();
      return new Promise<void>((resolve) => {
        img.addEventListener('load', () => resolve(), { once: true });
        img.addEventListener('error', () => resolve(), { once: true });
      });
    });

    Promise.all(imagePromises).then(() => {
      win.requestAnimationFrame(() => {
        win.setTimeout(() => {
          win.focus();
          win.print();
        }, delayMs);
      });
    });
  };

  if (win.document.readyState === 'complete') {
    printWhenReady();
  } else {
    win.addEventListener('load', printWhenReady, { once: true });
  }
}

export function openPrintWindow(title: string, bodyHtml: string, extraCss = '') {
  const win = openBlankPrintWindow(title);
  writePrintWindow(win, title, bodyHtml, extraCss);
  return win;
}
