import SwiftUI

@main
struct SaySoApp: App {
    init() { Theme.registerFonts() }

    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}

/// Splash for a moment, onboarding the first time, then the app.
struct RootView: View {
    @AppStorage("onboarded") private var onboarded = false
    @State private var splash = true

    var body: some View {
        ZStack {
            if splash {
                WelcomeSplash().transition(.opacity)
            } else if !onboarded {
                WelcomeOnboarding { withAnimation { onboarded = true } }.transition(.opacity)
            } else {
                TabView {
                    Tab("Chat", systemImage: "bubble.left.and.text.bubble.right") { ChatView() }
                    Tab("Styles", systemImage: "person.text.rectangle") { StylesView() }
                    Tab("Keyboard", systemImage: "keyboard") { KeyboardSettingsView() }
                    Tab("Setup", systemImage: "checklist") { SetupView() }
                }
                .transition(.opacity)
            }
        }
        .task {
            try? await Task.sleep(for: .seconds(1.2))
            withAnimation(.easeOut(duration: 0.4)) { splash = false }
        }
    }
}
