# WorkManager creates its Room database reflectively through
# Room.databaseBuilder(...).build(), which loads
# androidx.work.impl.WorkDatabase_Impl by name and invokes its no-arg
# constructor. Room only ships "-keep class * extends
# androidx.room.RoomDatabase", which preserves the class name but does not
# protect the constructor under R8 full mode. Without the constructor R8
# strips it and the app crashes before Application.onCreate with:
#
#   java.lang.RuntimeException: Unable to get provider
#   androidx.startup.InitializationProvider
#   Caused by: java.lang.NoSuchMethodException:
#   androidx.work.impl.WorkDatabase_Impl.<init> []
#
# Keep the constructors for every generated Room database implementation.
-keep class * extends androidx.room.RoomDatabase {
    <init>(...);
}
