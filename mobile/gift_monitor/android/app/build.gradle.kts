plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.telegram.giftmonitor.gift_monitor"
    compileSdk = 35  // Обновлено для совместимости с плагинами
    ndkVersion = "27.0.12077973"

    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        applicationId = "com.telegram.giftmonitor.gift_monitor"
        minSdk = 21
        targetSdk = 33  // ИЗМЕНЕНО с flutter.targetSdkVersion на 33 для совместимости с Android 14+
        versionCode = 1
        versionName = "1.0.0"
        
        // Поддержка многоязычности
        resourceConfigurations += listOf("en", "ru")
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
            
            // Оптимизация для release
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        
        debug {
            // Для отладки
            isDebuggable = true
            isMinifyEnabled = false
        }
    }
    
    // Опции упаковки
    packagingOptions {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    // Поддержка современных Java API на старых Android версиях
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.0.4")
    
    // WorkManager для фоновой работы (если будете использовать)
    implementation("androidx.work:work-runtime-ktx:2.9.0")
    
    // Для уведомлений
    implementation("androidx.core:core-ktx:1.12.0")
}