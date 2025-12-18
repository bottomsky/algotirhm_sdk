# PowerShell Pre-commit hook for naming convention checks
# Install with: Copy-Item scripts/pre-commit.ps1 .git/hooks/pre-commit

Write-Host "🔍 运行命名规范检查..." -ForegroundColor Cyan
python scripts/check_naming_convention.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 命名规范检查失败！请修复命名规范问题后再提交。" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 命名规范检查通过！" -ForegroundColor Green
exit 0
