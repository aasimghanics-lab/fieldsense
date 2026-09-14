export async function exportChart() {
  const svg = document.querySelector('.chart .recharts-surface');
  if (!svg) throw new Error('Load a chart before exporting.');
  const source = new XMLSerializer().serializeToString(svg);
  const url = URL.createObjectURL(new Blob([source], {type:'image/svg+xml'}));
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(image.width, 800) * 2;
    canvas.height = Math.max(image.height, 300) * 2;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Image export is unavailable in this browser.');
    context.fillStyle = '#fffefa';
    context.fillRect(0,0,canvas.width,canvas.height);
    context.drawImage(image,0,0,canvas.width,canvas.height);
    const link = document.createElement('a');
    link.download = 'fieldsense-chart.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  } finally { URL.revokeObjectURL(url); }
}
