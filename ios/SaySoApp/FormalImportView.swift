import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

enum FormalKind: String, Identifiable {
    case email, essay

    var id: String { rawValue }

    var title: String { self == .email ? "Add emails" : "Add essays & documents" }
    var guides: [SourceGuide] { self == .email ? SourceGuide.emails : SourceGuide.essays }
    var explanation: String {
        self == .email
            ? "Emails you sent yourself teach SaySo how you greet, ask and sign off, so its emails and official messages sound like you."
            : "Essays, papers and other texts you wrote teach SaySo your longer, formal voice for essays and official texts."
    }
}

/// Adding the user's own emails or essays to a style: pick the style, follow a guide, add screenshots, files or text.
struct FormalImportView: View {
    let kind: FormalKind
    var styleID: String? = nil
    let onDone: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var styles: [Style] = []
    @State private var target = SharedStore.styleID
    @State private var files: [Upload] = []
    @State private var pasted = ""
    @State private var picked: [PhotosPickerItem] = []
    @State private var importing = false
    @State private var pasting = false
    @State private var sending = false
    @State private var result: String?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section { Text(kind.explanation).font(.subheadline) }
                if styleID == nil, styles.count > 1 {
                    Picker("Add to style", selection: $target) {
                        ForEach(styles.filter(\.isReady)) { Text($0.name).tag($0.id) }
                    }
                }
                Section("How to get them") { SourceGuideList(guides: kind.guides) }
                Section {
                    PhotosPicker(selection: $picked, matching: .any(of: [.screenshots, .images])) {
                        Label("Add screenshots or photos", systemImage: "photo.on.rectangle")
                    }
                    Button { importing = true } label: { Label("Add files", systemImage: "doc.badge.plus") }
                    Button { pasting = true } label: { Label("Paste text", systemImage: "doc.on.clipboard") }
                    ForEach(Array(files.enumerated()), id: \.offset) { index, file in
                        Label(file.name, systemImage: file.mimeType.hasPrefix("image") ? "photo" : "doc.text")
                            .lineLimit(1)
                            .swipeActions { Button("Remove", role: .destructive) { files.remove(at: index) } }
                    }
                    if !pasted.isEmpty {
                        Label("Pasted text · \(pasted.split(separator: " ").count) words", systemImage: "text.alignleft")
                            .swipeActions { Button("Remove", role: .destructive) { pasted = "" } }
                    }
                } header: {
                    Text(kind == .email ? "Your emails" : "Your texts")
                } footer: {
                    Text("Only your own writing is kept. Screenshots and photos are read once and not stored.")
                }
                if let result { Section { Label(result, systemImage: "checkmark.circle.fill").foregroundStyle(.green) } }
                if let error { Section { Text(error).foregroundStyle(.red) } }
                Section {
                    Button {
                        Task { await send() }
                    } label: {
                        if sending {
                            ProgressView("Reading…").frame(maxWidth: .infinity)
                        } else {
                            Text(result == nil ? "Learn my \(kind == .email ? "email" : "formal") voice" : "Done")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(sending || (result == nil && files.isEmpty && pasted.isEmpty))
                }
            }
            .navigationTitle(kind.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
            .task {
                if let styleID { target = styleID }
                styles = (try? await SaySoAPI.styles()) ?? []
            }
            .fileImporter(isPresented: $importing, allowedContentTypes: allowedTypes, allowsMultipleSelection: true) { result in
                if case .success(let urls) = result { add(urls) }
            }
            .onChange(of: picked) { _, items in
                guard !items.isEmpty else { return }
                Task { await addImages(items) }
            }
            .sheet(isPresented: $pasting) {
                EditAnswerView(text: pasted) { text in
                    pasted = text
                    pasting = false
                }
            }
        }
    }

    private var allowedTypes: [UTType] {
        var types: [UTType] = [.plainText, .pdf]
        for ext in ["docx", "md", "mbox"] { if let type = UTType(filenameExtension: ext) { types.append(type) } }
        return types
    }

    private func add(_ urls: [URL]) {
        for url in urls {
            let scoped = url.startAccessingSecurityScopedResource()
            defer { if scoped { url.stopAccessingSecurityScopedResource() } }
            if let data = try? Data(contentsOf: url) {
                let type = UTType(filenameExtension: url.pathExtension)?.preferredMIMEType ?? "application/octet-stream"
                files.append(Upload(name: url.lastPathComponent, data: data, mimeType: type))
            }
        }
    }

    private func addImages(_ items: [PhotosPickerItem]) async {
        for (index, item) in items.enumerated() {
            if let data = try? await item.loadTransferable(type: Data.self) {
                files.append(Upload(name: String(format: "page%02d.jpg", files.count + index + 1), data: SaySoAPI.jpeg(data),
                                    mimeType: "image/jpeg"))
            }
        }
        picked = []
    }

    private func send() async {
        if result != nil {
            onDone()
            dismiss()
            return
        }
        sending = true
        defer { sending = false }
        do {
            try await SaySoAPI.addDocuments(to: target, files: files, text: pasted, kind: kind.rawValue)
            let style = try? await SaySoAPI.style(target)
            let count = style?.formal?.counts?[kind.rawValue] ?? 0
            var summary = kind == .email ? "Learned from \(count) of your emails" : "Learned from \(count) of your texts"
            if kind == .email, let openings = style?.formal?.profile?.openings, let first = openings.first {
                summary += " · you open with “\(first)”"
            }
            result = summary
            files = []
            pasted = ""
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
