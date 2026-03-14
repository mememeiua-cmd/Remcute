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
if [ -z "$JAVA_HOME" ] ; then
    echo "Error: JAVA_HOME is not set and no 'java' command could be found in your PATH."
    echo "Please set the JAVA_HOME variable in your environment to match the
    location of your Java installation."
    exit 1
fi

# Set default values for GRADLE_HOME if it is not already set
if [ -z "$GRADLE_HOME" ] ; then
    GRADLE_HOME="$APP_HOME/../../gradle"
fi

# Determine the start-up script to use
if [ -n "$GRADEL_STARTUP_SCRIPT" ] ; then
    START_UP_SCRIPT="$GRADEL_STARTUP_SCRIPT"
else
    START_UP_SCRIPT="$GRADLE_HOME/bin/gradle"
fi

# Set GRADLE_HOME to the Gradle home directory
export GRADLE_HOME

# Set up the Gradle executable
if [ -f "$START_UP_SCRIPT" ] ; then
    START_UP_SCRIPT="$START_UP_SCRIPT"
else
    START_UP_SCRIPT="$GRADLE_HOME/bin/gradle"
fi

# Set up the Java executable
if [ -z "$JAVA_EXE" ] ; then
    if [ -n "$JAVACMD" ] ; then
        JAVA_EXE="$JAVACMD"
    else
        JAVA_EXE="java"
    fi
fi

# Execute the Gradle start-up script
exec "$JAVA_EXE" -Xmx64m -Xms64m -XX:MaxPermSize=256m -XX:+HeapDumpOnOutOfMemoryError -Dfile.encoding=UTF-8 -Duser.country=US -Duser.language=en -Duser.variant -cp "$APP_HOME/../gradle/wrapper/gradle-wrapper.properties" org.gradle.wrapper.GradleWrapperMain "$@"
