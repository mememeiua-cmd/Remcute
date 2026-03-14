#!/bin/sh

##############################################################################
# Gradle start up script for POSIX
##############################################################################

# Resolve APP_HOME
app_path=$0
while [ -h "$app_path" ] ; do
    ls_out=$(ls -ld "$app_path")
    link=$(expr "$ls_out" : '.*-> \(.*\)$')
    if expr "$link" : '/.*' > /dev/null; then
        app_path="$link"
    else
        app_path=$(dirname "$app_path")/"$link"
    fi
done
APP_HOME=$(dirname "$app_path")

# Add the working directory to the whitelist
export GRADLE_USER_HOME="/root/.gradle"

# Check if Java is installed
if ! type -p java > /dev/null; then
    echo "JAVA_HOME is not set" >&2
    exit 1
fi

# Normalize JAVA_HOME
if [ -n "$JAVA_HOME" ]; then
    export JAVA_HOME="$JAVA_HOME"
fi

# Start the build
"$APP_HOME/gradle/wrapper/gradle-wrapper.properties"
