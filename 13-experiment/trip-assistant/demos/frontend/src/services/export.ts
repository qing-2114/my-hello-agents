/** 按 A4 可用高度逐页裁切，避免长行程只导出第一页。 */
export async function exportPlan(element: HTMLElement, filename: string, format: 'png' | 'pdf') {
  const { default: html2canvas } = await import('html2canvas')
  const mapElement = element.querySelector<HTMLElement>('[data-map-export]')
  let mapImage: string | undefined
  if (mapElement?.dataset.locations) {
    try {
      // WebGL 底图在 html2canvas 中可能为空白，改取同源的静态地图。
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}/map/static?locations=${encodeURIComponent(mapElement.dataset.locations)}`, { signal: AbortSignal.timeout(20000) })
      if (!response.ok || !response.headers.get('content-type')?.startsWith('image/')) throw new Error('静态地图不可用')
      const blob = await response.blob()
      mapImage = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.onerror = reject
        reader.readAsDataURL(blob)
      })
    } catch { /* 静态地图不可用时，在导出中保留坐标清单。 */ }
  }
  const coordinates = Array.from(element.querySelectorAll<HTMLElement>('[data-coordinate]'))
    .map(item => item.dataset.coordinate ?? '')
  const canvas = await html2canvas(element, {
    scale: 2, useCORS: true, allowTaint: false, backgroundColor: '#ffffff',
    onclone(doc) {
      doc.querySelectorAll<HTMLElement>('[data-export-hidden]').forEach(el => { el.style.display = 'none' })
      doc.querySelectorAll<HTMLImageElement>('img').forEach(img => { img.loading = 'eager' })
      const mapClone = doc.querySelector<HTMLElement>('[data-map-export]')
      if (mapClone) {
        mapClone.replaceChildren()
        if (mapImage) {
          const image = doc.createElement('img')
          image.src = mapImage
          image.style.cssText = 'width:100%;height:100%;object-fit:contain'
          mapClone.append(image)
        } else {
          mapClone.style.cssText = 'height:auto;padding:24px;background:#eaf0e7;border-radius:12px'
          const note = doc.createElement('p')
          note.textContent = '地图截图不可用，景点坐标参考：'
          mapClone.append(note)
        }
        const list = doc.createElement('p')
        list.textContent = coordinates.join('；') || '暂无景点坐标'
        list.style.cssText = 'font-size:12px;padding:12px;background:#fff'
        // 截图成功时清单位于地图后，保留地址作为静态备份。
        if (mapImage) mapClone.after(list)
        else mapClone.append(list)
      }
    }
  })
  if (format === 'png') {
    const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(
      value => value ? resolve(value) : reject(new Error('图片生成失败')), 'image/png'))
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.download = `${filename}.png`; link.href = url; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    return
  }
  const { default: jsPDF } = await import('jspdf')
  const pdf = new jsPDF('p', 'mm', 'a4')
  const width = 190
  const pageHeight = Math.floor(canvas.width * 277 / width)
  for (let y = 0; y < canvas.height; y += pageHeight) {
    if (y) pdf.addPage()
    const slice = document.createElement('canvas')
    slice.width = canvas.width; slice.height = Math.min(pageHeight, canvas.height - y)
    const context = slice.getContext('2d')
    if (!context) throw new Error('导出画布不可用')
    context.drawImage(canvas, 0, y, canvas.width, slice.height, 0, 0, canvas.width, slice.height)
    pdf.addImage(slice.toDataURL('image/png'), 'PNG', 10, 10, width, slice.height * width / canvas.width)
  }
  pdf.save(`${filename}.pdf`)
}
