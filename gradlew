#!/bin/sh
##############################################################################
# Gradle start up script for POSIX
##############################################################################

# Add default JVM options here. You can also use JAVA_OPTS and GRADLE_OPTS
# to pass JVM options to this script.
DEFAULT_JVM_OPTS=\"\"

# Use the maximum available, or set MAX_STOPPED if you have that much memory.
MAX_STOPPED=250

command=\"\$@\"

# Use the embedded JRE if it exists and JAVA_HOME is not set
if [ -n \"\$JAVA_HOME\" ]; then
  if [ -x \"\$JAVA_HOME/jre/bin/java\" ]; then
    JAVACMD=\"\$JAVA_HOME/jre/bin/java\"
  else
    JAVACMD=\"\$JAVA_HOME/bin/java\"
  fi
else
  if [ -x \"\$JAVACMD\" ]; then
    # do nothing
  else
    JAVACMD=\"java\"
  fi
fi

# For Cygwin, switch paths to Windows format before running java
if [ \"\$CYGWIN\" != \"\" ]; then
  # Convert the path to Windows format
  GRADLE_HOME=`cygpath --windows \$GRADLE_HOME`
  JAVACMD=`cygpath --windows \$JAVACMD`
fi

# Start the JVM
startOrgId=$1
org.gradle.appname=gradle
DEFAULT_JVM_OPTS=\"-Xmx64m\"
JAVACMD=\"$JAVACMD $DEFAULT_JVM_OPTS\"

# For Darwin, add options to specify how the application appears in the dock
if [ \"\$darwin\" != \"\" ]; then
  GRADLE_OPTS=\"$GRADLE_OPTS -Xdock:name=Gradle -Xdock:icon=$GRADLE_HOME/media/gradle.icns\"
fi

# Decode the current directory
BASE_DIR=`dirname \"$0\"`

# Make sure we have an absolute path
cd \"$BASE_DIR\"

# Put the contents of bootstrapping classpath in CLASSPATH variable for easy access
CP=.

# Check if we have the required Java version
TOOL_CHECK=\"java -version\" 2>&1 | head -n 1 |awk '{print \$3}' |awk -F\".\" '{if (\$2<5) print \"NO\"; else print \"YES\";}'

if [ \"$TOOL_CHECK\" = \"NO\" ]; then
  echo \"Java version is too low. Please use Java 11 or later.\"
  exit 1
fi

echo \"Starting Gradle Daemon...\"

# For other operating systems, add GRADLE_HOME/bin to PATH
export GRADLE_HOME
export GRADLE_HOME=\"\$GRADLE_HOME\"
export PATH=\"\$GRADLE_HOME/bin:\$PATH\"

# Let the caller decide if Gradle should use the current or a new daemon
DAEMON_ARGS=\"--configure-on-demand --no-parallel --no-daemon\"

CLASSPATH=\"$CP\"

JAVACMD=\"$JAVACMD $DEFAULT_JVM_OPTS $GRADLE_OPTS\"

# Determine the Java command to use to start the JVM.
if [ -n \"\$JAVACMD\" ]; then
  echo \"Using JAVA_HOME: \$JAVA_HOME\"
  echo \"Using GRADLE_HOME: \$GRADLE_HOME\"
  java_cmd=\"$JAVACMD\"
else
  if [ -n \"\$JAVA_HOME\" ]; then
    java_cmd=\"$JAVA_HOME/bin/java\"
  else
    java_cmd=\"java\"
  fi
fi

# Start the daemon
echo \"Starting daemon...\"
echo \"$java_cmd $DAEMON_ARGS -Dorg.gradle.appname=gradlew -Dorg.gradle.jvmargs='-Xmx64m' -classpath\"
$java_cmd $DAEMON_ARGS -Dorg.gradle.appname=gradlew -Dorg.gradle.jvmargs='-Xmx64m' -classpath \"$CLASSPATH\" org.gradle.launcher.daemon.bootstrap.GradleDaemon 1.0-SNAPSHOT \"$@\"
