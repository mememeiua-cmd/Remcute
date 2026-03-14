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

# Use the embedded JRE if it exists and JAVA_HOME is not set.
if [ -z \"\$JAVA_HOME\" ]; then
  if [ -n \"\$JDK_HOME\" ]; then
    JAVA_HOME=\"\$JDK_HOME\"
  elif [ -n \"\$JRE_HOME\" ]; then
    JAVA_HOME=\"\$JRE_HOME\"
  fi
fi

# If JAVA_HOME is not set, use the default JDK under /usr/lib.
if [ -z \"\$JAVA_HOME\" ]; then
  JAVA_HOME=\"/usr/lib/jvm/default-java\"
fi

# Determine the Java command to use to start the JVM.
if [ -n \"\$JAVACMD\" ]; then
  # IBM's JDK on AIX uses strange paths and doesn't expand variables
  # in its .profile so we have to use cat to get it to work.
  JAVA_CMD=\"\$JAVACMD\"
elif [ -z \"\$JAVA_HOME\" ]; then
  # No JAVA_HOME set, use the system default java command.
  JAVA_CMD=\"java\"
else
  # JAVA_HOME is set, use that Java.
  JAVA_CMD=\"\$JAVA_HOME/bin/java\"
fi

# Set the default GRADLE_OPTS.
if [ -z \"\$GRADLE_OPTS\" ]; then
  GRADLE_OPTS=\"-Xmx64m -Xms64m\"
fi

# Set GRADLE_APP_NAME if it hasn't been set yet.
if [ -z \"\$GRADLE_APP_NAME\" ]; then
  GRADLE_APP_NAME=\"Gradle\"
fi

# Determine the start-up command.
STARTUP_CMD=\"$JAVA_CMD $DEFAULT_JVM_OPTS $JAVA_OPTS $GRADLE_OPTS -classpath \\\"\$CLASSPATH\\\" -Dorg.gradle.appname=\"$GRADLE_APP_NAME\" -Dorg.gradle.gradlehome=\"$GRADLE_HOME\" org.gradle.wrapper.GradleWrapperMain \$command\"

# Use -XX:+HeapDumpOnOutOfMemoryError to dump the heap when we run out of memory.
# This is just a nice thing to have for debugging OOMs, but it can be
# configured as needed.
# (See: http:// blogs.sun.com/alanb/entry/heap_dumps_on_out_of)
if [ \"\$MEMORY_SETTINGS\" != \"\" ]; then
  STARTUP_CMD=\"$STARTUP_CMD -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=dump.hprof\"
fi

# For Cygwin, switch paths to Windows format before running java
if [ \"\$CYGWIN\" != \"\" ]; then
  APP_HOME=`cygpath --dos --mixed \$APP_HOME`
  GRADLE_HOME=`cygpath --dos --mixed \$GRADLE_HOME`
  CLASSPATH=`cygpath --dos --mixed \$CLASSPATH`
  STARTUP_CMD=\"cmd /c \\\"$STARTUP_CMD\\\"\"
fi

# For Darwin, ensure the java executable is started with the correct working directory.
if [ \"\$DARWIN\" != \"\" ]; then
  STARTUP_CMD=\"$STARTUP_CMD --workdir \$APP_HOME\"
fi

# Start the JVM.
cd \"$APP_HOME\"
$STARTUP_CMD
