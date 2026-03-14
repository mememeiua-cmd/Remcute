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
APP_HOME=$(cd "$APP_HOME" && pwd)

APP_NAME="Gradle"
APP_BASE_NAME=$(basename "$0")

# JVM options - no inner quotes needed here
DEFAULT_JVM_OPTS="-Xmx64m -Xms64m"

CLASSPATH=$APP_HOME/gradle/wrapper/gradle-wrapper.jar

# Determine Java command
if [ -n "$JAVA_HOME" ] ; then
    JAVACMD="$JAVA_HOME/bin/java"
else
    JAVACMD=java
fi

if [ ! -x "$JAVACMD" ] && ! command -v "$JAVACMD" > /dev/null 2>&1; then
    echo "ERROR: JAVA_HOME is not set and no 'java' command found." >&2
    exit 1
fi

exec "$JAVACMD" \
    $DEFAULT_JVM_OPTS \
    $JAVA_OPTS \
    $GRADLE_OPTS \
    "-Dorg.gradle.appname=$APP_BASE_NAME" \
    -classpath "$CLASSPATH" \
    org.gradle.wrapper.GradleWrapperMain \
    "$@"
