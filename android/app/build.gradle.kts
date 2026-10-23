import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Per-developer settings from android/local.properties (gitignored), e.g. macIp=192.168.1.20
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "com.nathan.chesscamera"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.nathan.chesscamera"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        // Default IP of the Mac running receiver.py on a real phone; can be changed in the app (the emulator defaults to 10.0.2.2)
        buildConfigField("String", "MAC_IP", "\"${localProps.getProperty("macIp", "")}\"")
    }

    buildFeatures {
        buildConfig = true
    }

    // Shared debug key checked into the repo, so builds from any Mac can install over each other on the same phone
    signingConfigs {
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("debug")
        }
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")

    // CameraX
    val cameraxVersion = "1.4.2"  // 1.4+ ships 16 KB-aligned native libs (needed on 16 KB-page devices)
    implementation("androidx.camera:camera-core:$cameraxVersion")
    implementation("androidx.camera:camera-camera2:$cameraxVersion")
    implementation("androidx.camera:camera-lifecycle:$cameraxVersion")
    implementation("androidx.camera:camera-view:$cameraxVersion")
}