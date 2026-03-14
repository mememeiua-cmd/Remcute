#!/bin/bash
set -e
git remote set-url origin "https://${GITHUB_PERSONAL_ACCESS_TOKEN}@github.com/mememeiua-cmd/Remcute.git"
git push origin main
git remote set-url origin "https://github.com/mememeiua-cmd/Remcute"
echo "Done"
