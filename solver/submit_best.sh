#!/usr/bin/env bash
# Verify BEST.txt end to end, write submission.csv and submit it to Kaggle with a message.
# usage: submit_best.sh PUZZLES.csv BEST.txt OUT.csv "message"
set -e
cd "$(dirname "$0")"
python3 -I -c "
import sys; sys.path.insert(0,'.'); import elf
P=elf.load_puzzles('$1'); B=elf.read_progs_txt('$2')
sc=elf.write_submission(P,B,'$3'); c=elf.load_submission('$3')
assert set(c)==set(P) and all(elf.check_program(P[k],v)[0] for k,v in c.items())
print('verified', sc)"
kaggle competitions submit -c santa-2026 -f "$3" -m "$4" 2>&1 | tail -1
sleep 30
kaggle competitions submissions -c santa-2026 2>&1 | sed -n 3p | cut -c1-180
