import SwiftUI

@main
struct SaySoApp: App {
    var body: some Scene {
        WindowGroup {
            TabView {
                Tab("Styles", systemImage: "person.text.rectangle") { StylesView() }
                Tab("Chat", systemImage: "bubble.left.and.text.bubble.right") { ChatView() }
                Tab("Keyboard", systemImage: "keyboard") { KeyboardSettingsView() }
                Tab("Setup", systemImage: "checklist") { SetupView() }
            }
        }
    }
}
