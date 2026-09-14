export async function exportChart() {
  const original = document.querySelector<SVGSVGElement>('.chart .recharts-surface');
  if (!original) throw new Error('Load a chart before exporting.');
  const bounds = original.getBoundingClientRect();
  const width = Math.round(bounds.width);
  const height = Math.round(bounds.height);
  if (!width || !height) throw new Error('The chart is not visible.');
  const svg = original.cloneNode(true) as SVGSVGElement;
  svg.setAttribute('width', String(width));
  svg.setAttribute('height', String(height));
  svg.style.width = width + 'px';
  svg.style.height = height + 'px';
  const source = new XMLSerializer().serializeToString(svg);
  const url = URL.createObjectURL(new Blob([source], {type:'image/svg+xml;charset=utf-8'}));
  try {
    const image = new Image();
    await new Promise<void>((resolve,reject)=>{image.onload=()=>resolve();image.onerror=()=>reject(new Error('Could not render the chart image.'));image.src=url;});
    const canvas = document.createElement('canvas');
    canvas.width=width*2;canvas.height=height*2;
    const context=canvas.getContext('2d');
    if (!context) throw new Error('Image export is unavailable in this browser.');
    context.fillStyle='#fffefa';context.fillRect(0,0,canvas.width,canvas.height);
    context.drawImage(image,0,0,canvas.width,canvas.height);
    const png=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('PNG encoding failed.')),'image/png'));
    const downloadUrl=URL.createObjectURL(png);
    const link=document.createElement('a');
    link.download='fieldsense-chart.png';link.href=downloadUrl;
    document.body.appendChild(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(downloadUrl),10000);
  } finally { URL.revokeObjectURL(url); }
}
