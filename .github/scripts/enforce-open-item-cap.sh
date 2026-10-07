#!/usr/bin/env bash
# Close a new issue or pull request when its author already has CAP open ones.
#
# One account once opened 57 pull requests and 11 issues in two weeks, almost all
# of them self-paired AI output, and review capacity became the bottleneck. The
# open items are counted through GraphQL connections, not the search API: search
# lags by seconds, and a burst of five items would each see a stale count.
set -euo pipefail

: "${REPO:?}" "${AUTHOR:?}" "${NUMBER:?}" "${KIND:?}"
CAP="${CAP:-10}"
EXEMPT="${EXEMPT:-}"

author_lc="${AUTHOR,,}"
# The login goes into a jq filter below, so refuse anything but a login's alphabet.
[[ "$author_lc" =~ ^[a-z0-9-]+(\[bot\])?$ ]] || { echo "unexpected login: $AUTHOR" >&2; exit 1; }

for name in $EXEMPT; do
  if [[ "${name,,}" == "$author_lc" ]]; then
    echo "$AUTHOR is exempt from the open-item cap"
    exit 0
  fi
done

count_open() {
  local query='query($owner:String!,$name:String!,$endCursor:String){repository(owner:$owner,name:$name){CONN(states:OPEN,first:100,after:$endCursor){nodes{author{login}}pageInfo{hasNextPage endCursor}}}}'
  query="${query//CONN/$1}"
  gh api graphql --paginate -f query="$query" -f owner="${REPO%%/*}" -f name="${REPO##*/}" \
    --jq ".data.repository.$1.nodes | map(select((.author.login // \"\" | ascii_downcase) == \"$author_lc\")) | length" |
    awk '{ total += $1 } END { print total + 0 }'
}

open_issues="$(count_open issues)"
open_prs="$(count_open pullRequests)"
total=$((open_issues + open_prs))
echo "$AUTHOR has $total open items ($open_issues issues, $open_prs pull requests); cap is $CAP"

if ((total <= CAP)); then
  exit 0
fi

message="Thanks for the contribution. To keep review manageable, one author can have at most $CAP open issues and pull requests combined (you have $total, including this one). Please let some of the earlier ones be merged or closed, then re-open or re-submit this one. A closed item can always be reopened once there is room.

为了让评审跟得上，同一位作者同时最多保留 $CAP 个未关闭的 issue 和 PR（合计，你现在有 $total 个，包含本条）。请等之前的被合并或关闭后，再重新打开或提交本条。有空位后可随时 reopen。"

if [[ "$KIND" == "pr" ]]; then
  gh pr close "$NUMBER" --repo "$REPO" --comment "$message"
else
  gh issue close "$NUMBER" --repo "$REPO" --reason "not planned" --comment "$message"
fi
