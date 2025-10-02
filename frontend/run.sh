current_dir=$(basename "$PWD")

if [[ "$current_dir" == "later-system" ]]; then
    cd frontend
fi

pnpm i

if [ ! -d ../.logs ]; then
    mkdir ../.logs
fi

log_file="../.logs/frontend.log"
: > "$log_file"

if [[ "$1" == "--prod" ]]; then
    pnpm build
    pnpm run start 2>&1 | tee -a "$log_file"
else
    pnpm dev 2>&1 | tee -a "$log_file"
fi
