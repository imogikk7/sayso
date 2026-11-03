import SwiftUI

// The Styles tab split by kind of text (Messages · Emails · Essays), each with its own traits, and the lists the user
// can edit by hand: greetings and sign-offs for emails, phrases they never use. Saved on the server (custom.json).

/// The three kinds of text a style writes; each has its own section in the Styles tab.
enum StyleKind: String, CaseIterable, Identifiable {
    case messages, emails, essays

    var id: String { rawValue }

    var title: String {
        switch self {
        case .messages: "Messages"
        case .emails: "Emails"
        case .essays: "Essays"
        }
    }

    var icon: String {
        switch self {
        case .messages: "bubble.left.and.bubble.right.fill"
        case .emails: "envelope.fill"
        case .essays: "doc.text.fill"
        }
    }

    var gradient: LinearGradient {
        switch self {
        case .messages: StylePalette.messages
        case .emails: StylePalette.emails
        case .essays: StylePalette.essays
        }
    }
}

/// Big tabs at the top of the Styles tab: one per kind of text, with how much SaySo has of it.
struct StyleKindTabs: View {
    @Binding var selection: StyleKind
    let counts: [StyleKind: Int]
    @Namespace private var pill

    var body: some View {
        HStack(spacing: 4) {
            ForEach(StyleKind.allCases) { kind in
                tab(kind)
            }
        }
        .padding(5)
        .background(.regularMaterial, in: .rect(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(Color.primary.opacity(0.06)))
        .shadow(color: Theme.glow.opacity(0.18), radius: 12, y: 6)
    }

    private func tab(_ kind: StyleKind) -> some View {
        let selected = kind == selection
        return Button {
            withAnimation(.snappy(duration: 0.28)) { selection = kind }
        } label: {
            VStack(spacing: 4) {
                Image(systemName: kind.icon).font(.system(size: 16, weight: .semibold))
                Text(kind.title).font(Theme.label(14)).lineLimit(1).minimumScaleFactor(0.8)
                Text(countText(kind))
                    .font(.caption2.weight(.semibold))
                    .monospacedDigit()
                    .lineLimit(1)
                    .opacity(selected ? 0.85 : 0.6)
            }
            .foregroundStyle(selected ? Color.white : Color.primary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background {
                if selected {
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .fill(kind.gradient)
                        .matchedGeometryEffect(id: "selected", in: pill)
                        .shadow(color: Color.accentColor.opacity(0.35), radius: 8, y: 4)
                }
            }
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func countText(_ kind: StyleKind) -> String {
        let count = counts[kind] ?? 0
        return count > 0 ? "\(count)" : "Teach me"
    }
}

// MARK: - Lists the user edits

/// A list the user can edit by hand, and where it is stored on the server (custom.json: kind → field).
enum CustomList: String, Identifiable, CaseIterable {
    case openers, signoffs, emailAvoid, essayAvoid, messageAvoid

    var id: String { rawValue }

    var kind: String {
        switch self {
        case .openers, .signoffs, .emailAvoid: "email"
        case .essayAvoid: "essay"
        case .messageAvoid: "message"
        }
    }

    var field: String {
        switch self {
        case .openers: "openers"
        case .signoffs: "signoffs"
        case .emailAvoid, .essayAvoid, .messageAvoid: "avoid"
        }
    }

    /// The field holding the list's default item; nil for lists without one.
    var defaultField: String? {
        switch self {
        case .openers: "default_opener"
        case .signoffs: "default_signoff"
        case .emailAvoid, .essayAvoid, .messageAvoid: nil
        }
    }

    var isAvoid: Bool { defaultField == nil }

    var title: String {
        switch self {
        case .openers: "Opens with"
        case .signoffs: "Signs off with"
        case .emailAvoid: "Never in my emails"
        case .essayAvoid: "Never in my essays"
        case .messageAvoid: "Phrases I never use"
        }
    }

    var icon: String {
        switch self {
        case .openers: "hand.wave.fill"
        case .signoffs: "signature"
        case .emailAvoid, .essayAvoid, .messageAvoid: "nosign"
        }
    }

    var placeholder: String {
        switch self {
        case .openers: "Add a greeting, e.g. Hi [Name],"
        case .signoffs: "Add a sign-off, e.g. Best,"
        case .emailAvoid: "e.g. I hope this email finds you well"
        case .essayAvoid: "e.g. In today's world"
        case .messageAvoid: "e.g. LOL"
        }
    }

    var emptyText: String {
        switch self {
        case .openers: "No greetings yet. Add your emails or type the ones you use."
        case .signoffs: "No sign-offs yet. Add your emails or type the ones you use."
        case .emailAvoid, .essayAvoid, .messageAvoid: "Nothing yet. Add words or phrases SaySo should never write for you."
        }
    }

    var hint: String {
        switch self {
        case .openers, .signoffs:
            "Write [Name] where the person's name goes. Keep one per language: SaySo picks the one in the email's language, the default first."
        case .emailAvoid, .essayAvoid, .messageAvoid:
            "SaySo never writes these for you, whatever the model would say."
        }
    }
}

extension Style {
    /// The list as the user saved it; nil if they never edited it.
    func customItems(_ list: CustomList) -> [String]? {
        switch list {
        case .openers: custom?.email?.openers
        case .signoffs: custom?.email?.signoffs
        case .emailAvoid: custom?.email?.avoid
        case .essayAvoid: custom?.essay?.avoid
        case .messageAvoid: custom?.message?.avoid
        }
    }

    func customDefault(_ list: CustomList) -> String? {
        switch list {
        case .openers: custom?.email?.defaultOpener
        case .signoffs: custom?.email?.defaultSignoff
        case .emailAvoid, .essayAvoid, .messageAvoid: nil
        }
    }

    /// What SaySo found in the user's own emails (greetings and sign-offs, most used first).
    func parsedItems(_ list: CustomList) -> [String] {
        switch list {
        case .openers: formal?.openers ?? formal?.profile?.openings ?? []
        case .signoffs: formal?.signoffs ?? formal?.profile?.closings ?? []
        case .emailAvoid, .essayAvoid, .messageAvoid: []
        }
    }

    /// What the list shows: the user's own version, or what SaySo found.
    func shownItems(_ list: CustomList) -> [String] { customItems(list) ?? parsedItems(list) }
}

/// One editable list on the Styles tab: its items (the default marked) and an Edit button.
struct CustomListCard: View {
    let list: CustomList
    let items: [String]
    let defaultItem: String?
    let isCustom: Bool
    let onEdit: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 10) {
                Image(systemName: list.icon)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Color.accentColor)
                    .frame(width: 32, height: 32)
                    .background(Color.accentColor.opacity(0.12), in: .rect(cornerRadius: Theme.card, style: .continuous))
                VStack(alignment: .leading, spacing: 1) {
                    Text(list.title).font(Theme.label(16)).foregroundStyle(.primary)
                    if let source {
                        Text(source).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Spacer(minLength: 8)
                Button(action: onEdit) {
                    Label("Edit", systemImage: "pencil")
                        .font(.footnote.weight(.semibold))
                        .padding(.horizontal, 12).padding(.vertical, 6)
                        .foregroundStyle(Color.accentColor)
                        .background(Color.accentColor.opacity(0.12), in: .capsule)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Edit \(list.title)")
            }
            if items.isEmpty {
                Text(list.emptyText).font(.footnote).foregroundStyle(.secondary)
            } else if list.isAvoid {
                StyleFlowLayout(spacing: 8) {
                    ForEach(items, id: \.self) { item in
                        StyleChip(text: item, icon: "nosign")
                    }
                }
            } else {
                VStack(spacing: 8) {
                    ForEach(ordered, id: \.self) { item in
                        row(item)
                    }
                }
            }
        }
        .glassCard(radius: 20, padding: 16)
    }

    private var source: String? {
        if isCustom { return "Set by you" }
        return items.isEmpty ? nil : "Found in your emails"
    }

    /// The default first, as the writer uses them.
    private var ordered: [String] {
        guard let defaultItem, items.contains(defaultItem) else { return items }
        return [defaultItem] + items.filter { $0 != defaultItem }
    }

    private func row(_ item: String) -> some View {
        HStack(spacing: 10) {
            Text(item)
                .font(.subheadline)
                .foregroundStyle(.primary)
                .lineLimit(2)
                .frame(maxWidth: .infinity, alignment: .leading)
            if item == defaultItem {
                StyleStatusChip(text: "Default", icon: "star.fill", filled: true)
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .background(Color.accentColor.opacity(item == defaultItem ? 0.1 : 0.05),
                    in: .rect(cornerRadius: Theme.card, style: .continuous))
    }
}

/// Edits one list: add, remove (swipe or the red button), reorder (drag), mark one as the default; then saves it.
struct CustomListEditor: View {
    let list: CustomList
    let styleID: String
    let parsed: [String]
    let canReset: Bool
    let onSaved: (Style) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var items: [String]
    @State private var defaultItem: String?
    @State private var draft = ""
    @State private var saving = false
    @State private var error: String?

    private static let maxItems = 20
    private static let maxChars = 80

    init(list: CustomList, styleID: String, items: [String], defaultItem: String?, parsed: [String], canReset: Bool,
         onSaved: @escaping (Style) -> Void) {
        self.list = list
        self.styleID = styleID
        self.parsed = parsed
        self.canReset = canReset
        self.onSaved = onSaved
        _items = State(initialValue: items)
        _defaultItem = State(initialValue: defaultItem)
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(spacing: 10) {
                        TextField(list.placeholder, text: $draft)
                            .submitLabel(.done)
                            .onSubmit(add)
                        Button(action: add) {
                            Image(systemName: "plus.circle.fill").font(.title2)
                        }
                        .buttonStyle(.borderless)
                        .disabled(cleaned(draft).isEmpty || items.count >= Self.maxItems)
                        .accessibilityLabel("Add")
                    }
                } footer: {
                    Text(list.hint)
                }
                Section {
                    if items.isEmpty {
                        Text("Nothing here yet.").foregroundStyle(.secondary)
                    }
                    ForEach(items, id: \.self) { item in
                        row(item)
                    }
                    .onMove { from, to in items.move(fromOffsets: from, toOffset: to) }
                    .onDelete(perform: remove)
                } footer: {
                    Text(list.isAvoid ? "Swipe or tap − to remove."
                                      : "Tap ☆ to make one the default. Drag to reorder, tap − to remove.")
                }
                if canReset || (!parsed.isEmpty && items != parsed) {
                    Section {
                        Button("Go back to what SaySo found", role: .destructive) {
                            Task { await save(reset: true) }
                        }
                    } footer: {
                        Text(parsed.isEmpty ? "Clears this list." : "Uses the greetings and sign-offs from your own emails again.")
                    }
                }
                if let error {
                    Section {
                        Label(error, systemImage: "exclamationmark.triangle.fill")
                            .font(.footnote)
                            .foregroundStyle(.orange)
                    }
                }
            }
            .environment(\.editMode, .constant(.active))
            .scrollContentBackground(.hidden)
            .background(Theme.backdrop)
            .navigationTitle(list.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if saving {
                        ProgressView()
                    } else {
                        Button("Save") { Task { await save() } }
                            .fontWeight(.semibold)
                    }
                }
            }
            .interactiveDismissDisabled(saving)
        }
    }

    private func row(_ item: String) -> some View {
        HStack(spacing: 10) {
            Text(item)
                .frame(maxWidth: .infinity, alignment: .leading)
            if !list.isAvoid {
                let isDefault = item == defaultItem
                Button {
                    defaultItem = isDefault ? nil : item
                } label: {
                    Image(systemName: isDefault ? "star.fill" : "star")
                        .foregroundStyle(isDefault ? Color.accentColor : Color.secondary)
                }
                .buttonStyle(.borderless)
                .accessibilityLabel(isDefault ? "Default" : "Make default")
            }
        }
    }

    private func cleaned(_ text: String) -> String {
        String(text.split(whereSeparator: \.isWhitespace).joined(separator: " ").prefix(Self.maxChars))
    }

    private func add() {
        let item = cleaned(draft)
        guard !item.isEmpty, items.count < Self.maxItems else { return }
        if !items.contains(where: { $0.caseInsensitiveCompare(item) == .orderedSame }) {
            withAnimation { items.append(item) }
        }
        draft = ""
    }

    private func remove(_ offsets: IndexSet) {
        let removed = offsets.map { items[$0] }
        items.remove(atOffsets: offsets)
        if let defaultItem, removed.contains(defaultItem) { self.defaultItem = nil }
    }

    private func save(reset: Bool = false) async {
        if !reset { add() }  // a greeting typed but not added yet still counts
        saving = true
        error = nil
        defer { saving = false }
        do {
            let style = try await SaySoAPI.updateCustomList(
                styleID, kind: list.kind, field: list.field, items: reset ? nil : items,
                defaultField: list.defaultField, defaultValue: reset ? nil : defaultItem)
            onSaved(style)
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

// MARK: - Emails and essays

/// The top of the Emails or Essays section: how many texts SaySo learned from, on the kind's gradient.
struct KindSummaryCard: View {
    let kind: StyleKind
    let count: Int
    let unit: String
    let line: String

    var body: some View {
        HStack(alignment: .center, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text("\(count)")
                        .font(Theme.display(44))
                        .foregroundStyle(.white)
                        .minimumScaleFactor(0.6)
                        .lineLimit(1)
                    Text(unit).font(Theme.label(15)).foregroundStyle(.white.opacity(0.85))
                }
                Text(line).font(.footnote).foregroundStyle(.white.opacity(0.85))
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            Image(systemName: kind.icon)
                .font(.system(size: 30, weight: .semibold))
                .foregroundStyle(.white.opacity(0.9))
                .frame(width: 60, height: 60)
                .background(Color.white.opacity(0.16), in: .rect(cornerRadius: 18, style: .continuous))
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background {
            ZStack(alignment: .topTrailing) {
                kind.gradient
                Circle()
                    .fill(Theme.glow.opacity(0.4))
                    .frame(width: 180, height: 180)
                    .blur(radius: 45)
                    .offset(x: 50, y: -70)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .shadow(color: Color.accentColor.opacity(0.3), radius: 16, y: 8)
    }
}

/// Nothing of this kind yet: a friendly "Teach me" card that opens the upload flow.
struct KindEmptyState: View {
    let kind: StyleKind
    let title: String
    let detail: String
    let button: String
    let action: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            StyleIconTile(icon: kind.icon, gradient: kind.gradient, size: 64)
                .padding(.top, 6)
            VStack(spacing: 6) {
                Text(title).font(Theme.display(20)).foregroundStyle(.primary).multilineTextAlignment(.center)
                Text(detail).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Button(action: action) {
                HStack(spacing: 6) {
                    Image(systemName: "plus").font(.subheadline.weight(.bold))
                    Text(button).font(Theme.label(15))
                }
                .foregroundStyle(.white)
                .padding(.horizontal, 20).padding(.vertical, 12)
                .background(Theme.accentGradient, in: .capsule)
                .shadow(color: Color.accentColor.opacity(0.35), radius: 8, y: 4)
            }
            .buttonStyle(.plain)
            .padding(.bottom, 4)
        }
        .frame(maxWidth: .infinity)
        .glassCard(radius: 24, padding: 22)
    }
}

/// How the user writes one formal kind of text: sentence and paragraph length, structure, voice, linking words.
struct FormalTraitsCard: View {
    let kind: FormalKind
    let profile: FormalProfile

    private let columns = [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            LazyVGrid(columns: columns, alignment: .leading, spacing: 10) {
                if let words = profile.sentenceWords {
                    TraitTile(icon: "text.alignleft", value: "~\(Int(words.rounded())) words", label: sentenceLabel(words))
                }
                if let words = profile.paragraphWords {
                    TraitTile(icon: "text.justify.left", value: "~\(Int(words.rounded())) words", label: "per paragraph")
                }
                if let perDoc = profile.paragraphsPerDoc {
                    TraitTile(icon: "list.number", value: paragraphsText(perDoc),
                              label: kind == .email ? "per email" : "per essay")
                }
                if let firstPerson = profile.firstPerson {
                    TraitTile(icon: "person.fill", value: firstPerson >= 0.03 ? "Personal" : "Impersonal",
                              label: firstPerson >= 0.03 ? "writes as \u{201C}I\u{201D}" : "rarely says \u{201C}I\u{201D}")
                }
            }
            if let connectors = profile.connectors, !connectors.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text(kind == .essay ? "Typical moves: how you link ideas" : "Linking words you use")
                        .font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    StyleFlowLayout(spacing: 6) {
                        ForEach(connectors, id: \.self) { word in
                            StyleChip(text: word, icon: "link")
                        }
                    }
                }
            }
        }
        .glassCard(radius: 20, padding: 16)
    }

    private func sentenceLabel(_ words: Double) -> String {
        if words < 12 { return "per sentence: short and direct" }
        if words < 20 { return "per sentence: medium" }
        return "per sentence: long, detailed"
    }

    private func paragraphsText(_ value: Double) -> String {
        let count = max(1, Int(value.rounded()))
        return count == 1 ? "1 paragraph" : "\(count) paragraphs"
    }
}

/// One trait as a small tile: an icon, a value and what it means.
struct TraitTile: View {
    let icon: String
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Image(systemName: icon).font(.subheadline.weight(.semibold)).foregroundStyle(Color.accentColor)
            Text(value).font(Theme.display(17)).foregroundStyle(Theme.navy).lineLimit(1).minimumScaleFactor(0.7)
            Text(label).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, minHeight: 92, alignment: .topLeading)
        .padding(12)
        .background(Color.accentColor.opacity(0.08), in: .rect(cornerRadius: Theme.card, style: .continuous))
    }
}
