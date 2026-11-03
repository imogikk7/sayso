import SwiftUI

@main
struct SaySoApp: App {
    init() {
        Theme.registerFonts()
        AppLanguage.install()
    }

    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}

/// The app's tabs; kept outside the screens so changing the language (which rebuilds them) stays on Settings.
enum AppTab: String {
    case chat, styles, keyboard, settings
}

/// Splash for a moment, onboarding the first time, then the app.
struct RootView: View {
    @AppStorage("onboarded") private var onboarded = false
    @AppStorage(AppLanguage.storageKey, store: SharedStore.defaults) private var language = AppLanguage.system.rawValue
    @SceneStorage("tab") private var tab = AppTab.chat
    @State private var splash = true

    private var locale: Locale { (AppLanguage(rawValue: language) ?? .system).locale }

    var body: some View {
        ZStack {
            if splash {
                SplashView().transition(.opacity)
            } else if !onboarded {
                WelcomeOnboarding { withAnimation { onboarded = true } }.transition(.opacity)
            } else {
                TabView(selection: $tab) {
                    Tab("Chat", systemImage: "bubble.left.and.text.bubble.right", value: AppTab.chat) { ChatView() }
                    Tab("Styles", systemImage: "person.text.rectangle", value: AppTab.styles) { StylesView() }
                    Tab("Keyboard", systemImage: "keyboard", value: AppTab.keyboard) { KeyboardSettingsView() }
                    Tab("Settings", systemImage: "gearshape", value: AppTab.settings) { SetupView() }
                }
                .transition(.opacity)
            }
        }
        // A new language rebuilds every screen, so strings kept in variables are read again in that language.
        .id(language)
        .environment(\.locale, locale)
        .task {
            try? await Task.sleep(for: .seconds(2.3))
            withAnimation(.easeOut(duration: 0.4)) { splash = false }
        }
    }
}
