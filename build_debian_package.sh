#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SCRIPT_NAME="$(basename "$0")"

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
    field_value=$(sed -n -E "s/^${field_name}:\s*([^\s]+)\s*$/\1/p" <"$SCRIPT_DIR/debian/DEBIAN/control")
    if [[ -z "$field_value" ]]; then
        log_error "Cannot extract package \"${field_name}\" from DEBIAN/control"
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

function help() {
    log "Helper script to build debian package"
    log "Usage: $SCRIPT_NAME [-h|--help]"
}

# parse/check cli arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
    -h | --help)
        help
        exit 0
        ;;
    *)
        log "ERROR: unknown option: $1"
        exit 1
        ;;
    esac
done

# check tools
assert_tool dpkg-deb

# build package
PKG_USR_DIR="$SCRIPT_DIR/debian/usr"
if [[ -e "$PKG_USR_DIR" ]]; then
    log_info "Cleanup $PKG_USR_DIR directory"
    rm -r "$PKG_USR_DIR"
fi
# copy scripts
log_info "Gather package content"
mkdir -p "$PKG_USR_DIR/bin"
cp --no-target-directory "$SCRIPT_DIR/geekworm-x735-fan.py" "$PKG_USR_DIR/bin/geekworm-x735-fan"
chmod +x "$PKG_USR_DIR/bin/geekworm-x735-fan"
mkdir -p "$PKG_USR_DIR/lib/systemd/system"
cp "$SCRIPT_DIR/systemd/"*.service "$PKG_USR_DIR/lib/systemd/system"

# build package
log_info "Build package"
PACKAGE_VERSION="$(get_debian_control_field "Version")"
PACKAGE_NAME="$(get_debian_control_field "Package")"
PACKAGE_ARCH="$(get_debian_control_field "Architecture")"
PACKAGE_BUILD_DIR="$SCRIPT_DIR/dist"
if [[ ! -e "$PACKAGE_BUILD_DIR" ]]; then
    mkdir "$PACKAGE_BUILD_DIR"
fi
PACKAGE_ARCHIVE="${PACKAGE_BUILD_DIR}/${PACKAGE_NAME}_${PACKAGE_VERSION}_${PACKAGE_ARCH}.deb"
dpkg-deb --root-owner-group --debug --build "$SCRIPT_DIR/debian" "$PACKAGE_ARCHIVE"
log_info "Complete"
