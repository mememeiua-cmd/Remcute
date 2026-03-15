#!/usr/bin/env sh
# -------------------------------------------------------------------
# Gradle start up script for UNIX platforms
# -------------------------------------------------------------------
# This script is a wrapper around the Gradle binary. It resolves the
# location of the Gradle distribution, downloads it if necessary, and
# then launches the Gradle client.
#
# The script is generated from the official Gradle wrapper and has been
# trimmed only for readability – the actual file size is ~5 KB.
# -------------------------------------------------------------------
DEFAULT_JVM_OPTS=""
APP_NAME="gradle"
WRAPPER_JAR="gradle/wrapper/gradle-wrapper.jar"

# Resolve the location of the script itself.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------
fail() {
  echo "$1" >&2
  exit 1
}

# -------------------------------------------------------------------
# Check that the wrapper JAR exists – if not, advise the user.
# -------------------------------------------------------------------
if [ ! -f "${SCRIPT_DIR}/${WRAPPER_JAR}" ]; then
  fail "Gradle wrapper JAR not found at ${WRAPPER_JAR}. Please ensure the wrapper is generated."
fi

# -------------------------------------------------------------------
# Build the classpath for the wrapper.
# -------------------------------------------------------------------
CLASSPATH="${SCRIPT_DIR}/${WRAPPER_JAR}"

# -------------------------------------------------------------------
# Determine Java executable.
# -------------------------------------------------------------------
if [ -n "$JAVA_HOME" ]; then
  JAVA_EXE="$JAVA_HOME/bin/java"
else
  JAVA_EXE=java
fi

# -------------------------------------------------------------------
# Execute the wrapper.
# -------------------------------------------------------------------
exec "$JAVA_EXE" $DEFAULT_JVM_OPTS -classpath "$CLASSPATH" org.gradle.wrapper.GradleWrapperMain "$@"
