# Render the simple checked-in SVG primitives to a standalone PNG on Windows.
# Uses System.Drawing only; no project dependencies or network calls.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
[xml]$diagram = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'architecture.svg') -Raw -Encoding UTF8
$bitmap = [System.Drawing.Bitmap]::new(2000, 1320)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
function BrushFor([string]$value) {
    return [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml($value))
}
try {
    foreach ($element in $diagram.SelectNodes('//*[local-name()="rect" or local-name()="line" or local-name()="polygon" or local-name()="text"]')) {
        $fill = $element.GetAttribute('fill')
        if (-not $fill) { $fill = '#172d3b' }
        if ($element.LocalName -eq 'rect') {
            $box = [System.Drawing.RectangleF]::new([float]$element.x, [float]$element.y, [float]$element.width, [float]$element.height)
            $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
            $radius = [float]$element.GetAttribute('rx')
            if ($radius -gt 0) {
                $diameter = 2 * $radius
                $path.AddArc($box.X, $box.Y, $diameter, $diameter, 180, 90)
                $path.AddArc($box.Right - $diameter, $box.Y, $diameter, $diameter, 270, 90)
                $path.AddArc($box.Right - $diameter, $box.Bottom - $diameter, $diameter, $diameter, 0, 90)
                $path.AddArc($box.X, $box.Bottom - $diameter, $diameter, $diameter, 90, 90)
                $path.CloseFigure()
            } else { $path.AddRectangle($box) }
            $brush = BrushFor $fill
            $graphics.FillPath($brush, $path)
            $brush.Dispose()
            if ($element.GetAttribute('stroke')) {
                $pen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml($element.GetAttribute('stroke')), [float]$element.GetAttribute('stroke-width'))
                $graphics.DrawPath($pen, $path)
                $pen.Dispose()
            }
            $path.Dispose()
        } elseif ($element.LocalName -eq 'line') {
            $pen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml($element.GetAttribute('stroke')), [float]$element.GetAttribute('stroke-width'))
            if ($element.GetAttribute('stroke-dasharray')) { $pen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dash }
            $graphics.DrawLine($pen, [float]$element.x1, [float]$element.y1, [float]$element.x2, [float]$element.y2)
            $pen.Dispose()
        } elseif ($element.LocalName -eq 'polygon') {
            [System.Drawing.PointF[]]$points = @($element.points.Split(' ') | ForEach-Object {
                $pair = $_.Split(',')
                [System.Drawing.PointF]::new([float]$pair[0], [float]$pair[1])
            })
            $brush = BrushFor $fill
            $graphics.FillPolygon($brush, $points)
            $brush.Dispose()
        } else {
            $style = [System.Drawing.FontStyle]::Regular
            if ($element.GetAttribute('font-weight') -eq '700') { $style = [System.Drawing.FontStyle]::Bold }
            $size = [float]$element.GetAttribute('font-size')
            $font = [System.Drawing.Font]::new('Segoe UI', $size, $style, [System.Drawing.GraphicsUnit]::Pixel)
            $ascent = $font.FontFamily.GetCellAscent($style) / $font.FontFamily.GetEmHeight($style) * $size
            $format = [System.Drawing.StringFormat]::GenericTypographic.Clone()
            $format.FormatFlags = $format.FormatFlags -bor [System.Drawing.StringFormatFlags]::MeasureTrailingSpaces
            $brush = BrushFor $fill
            $graphics.DrawString($element.InnerText, $font, $brush, [System.Drawing.PointF]::new([float]$element.x, [float]$element.y - $ascent), $format)
            $brush.Dispose()
            $font.Dispose()
            $format.Dispose()
        }
    }
    $bitmap.Save((Join-Path $PSScriptRoot 'architecture.png'), [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
