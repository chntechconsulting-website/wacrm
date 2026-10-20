[Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null

$pdfPath = "C:\Users\CHN\.gemini\antigravity\brain\338d3c93-3bd9-46d5-8e64-6d35c1716c28\.user_uploaded\media_1791866536114_5da6be4c.pdf"
$outPng = "C:\Users\CHN\Desktop\Wa CRM\backend\rendered_invoice.png"

$fileOp = [Windows.Storage.StorageFile]::GetFileFromPathAsync($pdfPath)
$file = $fileOp.GetAwaiter().GetResult()
$docOp = [Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)
$doc = $docOp.GetAwaiter().GetResult()
$page = $doc.GetPage(0)

$stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
$renderOp = $page.RenderToStreamAsync($stream)
$renderOp.GetAwaiter().GetResult()

$bytes = New-Object byte[] $stream.Size
$reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
$loadOp = $reader.LoadAsync($stream.Size)
$loadOp.GetAwaiter().GetResult()
$reader.ReadBytes($bytes)

[System.IO.File]::WriteAllBytes($outPng, $bytes)
Write-Host "Rendered PDF to PNG successfully! Size: $($bytes.Length) bytes"
