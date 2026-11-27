#!/bin/zsh
# Build the native CoreAudio / media-key helpers into bin/.
#   ./build.sh            build what's missing or older than its source
#   ./build.sh --force    rebuild everything
set -e
cd ${0:A:h}
for t in blackrec audiodev mediakey; do
  if [[ $1 == --force || ! -x bin/$t || src/$t.swift -nt bin/$t ]]; then
    echo "swiftc  src/$t.swift → bin/$t"
    swiftc -O -o bin/$t src/$t.swift
  else
    echo "ok      bin/$t"
  fi
done

# Python helper (loopend) runs in .venv
if [[ ! -x .venv/bin/python ]]; then
  echo "python  .venv (numpy)"
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
echo "ok      .venv"
