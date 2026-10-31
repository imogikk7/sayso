import SwiftUI
import UIKit

/// Setup checklist: add the keyboard, allow Full Access, set up Back Tap, test the server; plus the last replies.
struct SetupView: View {
    @State private var keyboardOpened = SharedStore.keyboardOpenedWithFullAccess
    @State private var shortcutDone = SharedStore.shortcutDone
    @State private var serverStatus: String?
    @State private var serverOK = false
    @State private var tryText = ""
    @State private var response = ReplyStore.latest

    var body: some View {
        NavigationStack {
            List {
                Section {
                    step(1, "Add the SaySo keyboard", done: keyboardOpened != nil,
                         detail: "Settings → General → Keyboard → Keyboards → Add New Keyboard → SaySo.")
                    step(2, "Allow Full Access", done: keyboardOpened != nil,
                         detail: "Tap SaySo in that list and turn on Allow Full Access, so it can reach your style. Then open the keyboard once, below.")
                    Button("Open Settings") {
                        if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                    }
                    TextField("Type here, then switch to SaySo 🌐", text: $tryText, axis: .vertical)
                        .lineLimit(1...4)
                } header: {
                    Text("Keyboard")
                }
                Section {
                    step(3, "Set up the Back Tap shortcut", done: shortcutDone, detail: """
                    Shortcuts → + → Take Screenshot → Reply from Screenshot (SaySo, leave Audience empty) → \
                    Choose from List → Copy to Clipboard. Then Settings → Accessibility → Touch → Back Tap → \
                    Double Tap → this shortcut.
                    """)
                    Toggle("I've set it up", isOn: $shortcutDone)
                        .onChange(of: shortcutDone) { _, value in SharedStore.shortcutDone = value }
                } header: {
                    Text("Reply from a screenshot")
                }
                Section {
                    step(4, "Check the connection", done: serverOK, detail: serverStatus ?? "Makes sure SaySo can reach your styles.")
                    Button("Test now") { Task { await test() } }
                } header: {
                    Text("Server")
                }
                if let response {
                    Section("Last screenshot replies") { RepliesView(response: response) }
                }
            }
            .navigationTitle("Setup")
            .onAppear {
                keyboardOpened = SharedStore.keyboardOpenedWithFullAccess
                response = ReplyStore.latest
            }
        }
    }

    private func step(_ number: Int, _ title: String, done: Bool, detail: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: done ? "checkmark.circle.fill" : "\(number).circle")
                .font(.title2)
                .foregroundStyle(done ? .green : .secondary)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.headline)
                Text(detail).font(.footnote).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 2)
    }

    private func test() async {
        serverStatus = "Testing…"
        let started = Date()
        do {
            let styles = try await SaySoAPI.styles()
            serverOK = true
            serverStatus = String(format: "Connected in %.1f s · %d style%@", Date().timeIntervalSince(started),
                                  styles.count, styles.count == 1 ? "" : "s")
        } catch {
            serverOK = false
            serverStatus = error.localizedDescription
        }
    }
}
