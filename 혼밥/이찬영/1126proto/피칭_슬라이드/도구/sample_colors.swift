// PNG 한 장에서 정해 둔 좌표의 색을 #RRGGBB로 출력한다 (macOS AppKit).
// swift sample_colors.swift p08.png
// 좌표는 960×540 기준. 피칭 PDF 8쪽에서 배경·남색 띠·패널 색을 뽑을 때 썼다.
import AppKit
let img = NSImage(contentsOfFile: CommandLine.arguments[1])!
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
for (x,y) in [(10,10),(100,530),(240,236),(480,300),(470,236),(420,103),(300,475),(910,486),(860,30),(30,52),(100,350)] {
  let c = rep.colorAt(x: x*rep.pixelsWide/960, y: y*rep.pixelsHigh/540)!.usingColorSpace(.sRGB)!
  print(x,y,String(format:"#%02X%02X%02X",Int(c.redComponent*255),Int(c.greenComponent*255),Int(c.blueComponent*255)))
}
