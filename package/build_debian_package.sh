#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCRIPT_NAME="$(basename "$0")"
SOURCE_DIR="$(dirname "${SCRIPT_DIR}")"

#
# Helper functions
#

function log() {
    echo "$*" >&2
}
function log_info() {
    log "INFO: $*"
}

function log_error() {
    log "ERROR: $*"
}

function get_debian_control_field() {
    local field_name="$1"
    local field_value
    field_value=$(sed -n -E "s/^${field_name}:\s*([^\s]+)\s*$/\1/p" <"$SCRIPT_DIR/debian/control")
    if [[ -z "$field_value" ]]; then
        log_error "Cannot extract package \"${field_name}\" from debian/control"
        exit 1
    fi
    echo "$field_value"
}

function assert_tool() {
    local tool_name="$1"
    if ! which "$tool_name" >/dev/null; then
        log_error "$tool_name is required, but isn't found!"
        exit 1
    fi
}

#
# CLI interface
#

function help() {
    log "Helper script to build debian package"
    log "Usage: $SCRIPT_NAME [-h|--help] [--dev-build)]"
}
DEV_BUILD=""
while [[ $# -gt 0 ]]; do
    case "$1" in
    -h | --help)
        help
        exit 0
        ;;
    --dev-build)
        DEV_BUILD="1"
        shift
        ;;
    *)
        log "ERROR: unknown option: $1"
        exit 1
        ;;
    esac
done

#
# main logic
#

cd "$SCRIPT_DIR"

# 1. build debian changelog from CHANGELOG.md
log_info "Generate dummy debian/changelog"
# read current maintainer
PACKAGE_MAINTAINER="$(sed -n -E -e 's/Maintainer:\s+(.*)/\1/p' debian/control)"
# read package name
PACKAGE_NAME="$(sed -n -E -e 's/Package:\s+(.*)/\1/p' debian/control)"
SOURCE_NAME="$(sed -n -E -e 's/Source:\s+(.*)/\1/p' debian/control)"
# read versions and release dates from CHANGELOG.md
readarray -t RELEASED_VERSIONS <<<"$(sed -n -E -e 's/^##\s*\[([0-9.]*)\][^0-9]*([0-9-]+)\s*$/\1:\2/p' "${SOURCE_DIR}/CHANGELOG.md")"
# add dummy release version if no versions are released
if [[ "${#RELEASED_VERSIONS[@]}" -eq 0 ]]; then
    RELEASED_VERSIONS+=("0.1.0-1:$(date '+%Y-%m-%d')")
fi
# override version (it can be used for dev package building)
if [[ "$DEV_BUILD" == 1 ]]; then
    LAST_VERSION="${RELEASED_VERSIONS[0]%:*}"
    NEXT_VERSION="$((${LAST_VERSION%%.*} + 1)).0.0-dev"
    RELEASED_VERSIONS=("$NEXT_VERSION:$(date '+%Y-%m-%d')" "${RELEASED_VERSIONS[@]}")
fi
# build changelog
DEBIAN_CHANGELOG_FILE="debian/changelog"
for RELEASE_IFNO in "${RELEASED_VERSIONS[@]}"; do
    RELEASE_VERSION="${RELEASE_IFNO%:*}"
    RELEASE_DATE="${RELEASE_IFNO#*:}"
    echo "${SOURCE_NAME} (${RELEASE_VERSION}) stable; urgency=medium"
    echo ""
    echo "  * Upstream release"
    echo ""
    echo "-- ${PACKAGE_MAINTAINER} $(date -d "$RELEASE_DATE" -u -R)"
    echo ""
done | head -n -1 >"${DEBIAN_CHANGELOG_FILE}"

# 2. run dpkg-buildpackage
log_info "Build package"
assert_tool dpkg-buildpackage
dpkg-buildpackage --build=binary --unsigned-source --unsigned-changes

## 3. move artifacts to dist
log_info "Move artifacts to dist directory"
OUTPUT_DIR="${SCRIPT_DIR}/dist"
if [[ -e "$OUTPUT_DIR" ]]; then
    rm -rf "$OUTPUT_DIR"
fi
mkdir "$OUTPUT_DIR"
mv "../${PACKAGE_NAME}_"* "$OUTPUT_DIR"
mv "../${SOURCE_NAME}_"* "$OUTPUT_DIR"

log_info "Complete!"
