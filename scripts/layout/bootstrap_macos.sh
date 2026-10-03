#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
layout_build="$repo_root/build/layout"
tool_prefix="$layout_build/tools/install"
mkdir -p "$layout_build/tools" "$layout_build/logs"
command -v brew >/dev/null
command -v uv >/dev/null
brew install tcl-tk@8 gnu-sed cairo libx11 libxext libxrender libsm libice > "$layout_build/logs/bootstrap-brew.log" 2>&1
uv venv --allow-existing "$layout_build/venv"
uv pip sync --python "$layout_build/venv/bin/python" "$repo_root/scripts/layout/requirements.lock.txt"
layout_sdk="${LAYOUT_SDKROOT:-$(/usr/bin/xcodebuild -version -sdk macosx Path)}"
tcl_prefix="$(brew --prefix tcl-tk@8)"
brew_prefix="$(brew --prefix)"
clone_pin() {
    local name="$1" url="$2" revision="$3" target="$layout_build/tools/$1"
    if [ ! -d "$target/.git" ]; then
        git init "$target"
        git -C "$target" remote add origin "$url"
        git -C "$target" fetch --depth 1 origin "$revision"
        git -C "$target" checkout --detach FETCH_HEAD
    fi
    test "$(git -C "$target" rev-parse HEAD)" = "$revision"
}
clone_pin magic https://github.com/RTimothyEdwards/magic.git 4f53bb3091d1e4a9b2009a58f157a8a4331d4c84
clone_pin netgen https://github.com/RTimothyEdwards/netgen.git 3cb047bd6b55ae09c8eefeb479b4fe746cfdb948
for tool in magic netgen; do
    (
        cd "$layout_build/tools/$tool"
        extras=()
        if [ "$tool" = magic ]; then
            extras=(--with-cairo="$brew_prefix/include" --enable-cairo-offscreen)
        fi
        SDKROOT="$layout_sdk" ./configure --prefix="$tool_prefix" \
            --with-tcl="$tcl_prefix/lib" --with-tk="$tcl_prefix/lib" \
            --x-includes="$brew_prefix/include" --x-libraries="$brew_prefix/lib" \
            "${extras[@]}" \
            CFLAGS="-I$brew_prefix/include -Wno-error=implicit-function-declaration" \
            LDFLAGS="-L$brew_prefix/lib" > "$layout_build/logs/$tool-configure.log" 2>&1
        SDKROOT="$layout_sdk" make -j8 > "$layout_build/logs/$tool-build.log" 2>&1
        make install > "$layout_build/logs/$tool-install.log" 2>&1
    )
done
"$layout_build/venv/bin/ciel" enable --pdk-root "$layout_build/pdk" --pdk-family gf180mcu \
    54435919abffb937387ec956209f9cf5fd2dfbee > "$layout_build/logs/ciel-install.log" 2>&1
"$tool_prefix/bin/magic" --version
"$tool_prefix/bin/netgen" -batch quit
printf 'Native analog tools and locked GF180MCU PDK are ready.\n'
