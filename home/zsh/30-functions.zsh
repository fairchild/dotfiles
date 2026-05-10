# 30-functions.zsh — interactive shell functions.
# Folded from live ~/.zshrc. Mathiasbynens-vintage .functions is in legacy/
# (most of it is python-2 era); resurrect entries here case-by-case.

# Run pytest for each src/*.py whose corresponding tests/test_*.py exists.
function run_pytest_for_changed_files() {
    local file test_file
    for file in $(find src tests -type f -name '*.py'); do
        if [[ "$file" == tests/* ]]; then
            pytest "$file"
        elif [[ "$file" == src/* ]]; then
            test_file="tests/$(basename "$file" | sed 's/^/test_/')"
            if [[ -f "$test_file" ]]; then
                pytest "$test_file"
            else
                echo "No corresponding test file found for $file"
            fi
        fi
    done
}

# Same loop, watched via entr.
function watch_tests() {
    find src tests -type f -name '*.py' | entr -c zsh -c '
        local file test_file
        for file in $(find src tests -type f -name "*.py"); do
            if [[ "$file" == tests/* ]]; then
                pytest "$file"
            elif [[ "$file" == src/* ]]; then
                test_file="tests/$(basename "$file" | sed "s/^/test_/")"
                if [[ -f "$test_file" ]]; then
                    pytest "$test_file"
                else
                    echo "No corresponding test file found for $file"
                fi
            fi
        done
    '
}

# Show recent local branches sorted by last commit, optionally filtered.
function latest() {
    local fmt='%(HEAD) %(color:yellow)%(refname:short)%(color:reset)%09%(color:reset) - %(contents:subject) - %(authorname) (%(color:green)%(committerdate:relative)%(color:reset))'
    if [[ $# -eq 1 ]]; then
        git for-each-ref --sort=committerdate refs/heads/ --format="$fmt" | grep $1
    else
        git for-each-ref --sort=committerdate refs/heads/ --format="$fmt"
    fi
}

# Set the terminal title manually.
title() {
    echo -ne "\033]0;$*\a"
}

# Live terminal title: "<dirname> — <command>" while running, then "<dirname>".
preexec() {
    local cmd="$1"
    if (( ${#cmd} > 30 )); then
        cmd="${cmd:0:27}..."
    fi
    print -Pn "\033]0;${PWD##*/} — $cmd\007"
}
precmd() {
    print -Pn "\033]0;${PWD##*/}\007"
}
