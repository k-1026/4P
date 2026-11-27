// 피칭 PDF를 쪽마다 PNG로 그리고 쪽 글자 앞부분을 출력한다 (macOS PDFKit, 따로 설치할 것 없음).
// swift render_pdf_pages.swift "혼밥 피피티.pdf" 출력폴더
// 슬라이드 크기(960×540pt)와 빈 자리 위치를 확인할 때 썼다.
import PDFKit
import AppKit
let args = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: args[1]))!
let outDir = args[2]
for i in 0..<doc.pageCount {
  let page = doc.page(at: i)!
  let b = page.bounds(for: .mediaBox)
  let scale: CGFloat = 1.0
  let img = NSImage(size: NSSize(width: b.width*scale, height: b.height*scale))
  img.lockFocus()
  NSColor.white.set(); NSRect(x:0,y:0,width:b.width*scale,height:b.height*scale).fill()
  let ctx = NSGraphicsContext.current!.cgContext
  ctx.scaleBy(x: scale, y: scale)
  page.draw(with: .mediaBox, to: ctx)
  img.unlockFocus()
  let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
  try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(outDir)/p\(String(format:"%02d", i+1)).png"))
  print("p\(i+1)", page.string?.prefix(200).replacingOccurrences(of: "\n", with: " | ") ?? "")
}
