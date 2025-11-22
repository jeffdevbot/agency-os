#!/bin/bash
# Pre-commit hook: Run TypeScript type check before allowing commit
# This catches type errors before they reach Render deployment

set -e

echo "🔍 Running TypeScript type check..."

# Change to frontend directory and run type check
cd frontend-web

# Run TypeScript compiler in check mode (no emit)
npx tsc --noEmit

if [ $? -eq 0 ]; then
  echo "✅ TypeScript check passed - no type errors found"
  exit 0
else
  echo "❌ TypeScript errors detected!"
  echo ""
  echo "Fix the type errors above before committing."
  echo "This prevents build failures on Render."
  exit 1
fi
