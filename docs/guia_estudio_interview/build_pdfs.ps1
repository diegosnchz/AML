$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$theme = Join-Path $root "pdf_theme.tex"

$docs = @(
    @{
        Input = Join-Path $root "README_PROYECTO.md"
        Output = Join-Path $root "README_PROYECTO.pdf"
        Title = "Guia completa del proyecto AML + Credit Risk Reporting"
        Subtitle = "Documento de estudio para entrevista"
    },
    @{
        Input = Join-Path $root "README_WEB.md"
        Output = Join-Path $root "README_WEB.pdf"
        Title = "Guia de la web y dashboards"
        Subtitle = "Pantallas, controles y explicacion sencilla"
    }
)

foreach ($doc in $docs) {
    pandoc $doc.Input `
        --from markdown `
        --to pdf `
        --pdf-engine=xelatex `
        --toc `
        --toc-depth=2 `
        --number-sections `
        --standalone `
        --include-in-header=$theme `
        --metadata title="$($doc.Title)" `
        --metadata subtitle="$($doc.Subtitle)" `
        --metadata author="AML Interview Demo" `
        --metadata date="" `
        --variable geometry:margin=2.2cm `
        --variable colorlinks=true `
        --variable linkcolor=AMLClay `
        --variable urlcolor=AMLClay `
        --variable documentclass=article `
        --output $doc.Output
}
