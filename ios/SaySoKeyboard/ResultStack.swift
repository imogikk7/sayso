import SwiftUI

/// Results in place of the keys (✨, the panel, the Back Tap shortcut's replies): each variant a neutral card on the
/// keyboard backdrop; a series is a stack of messages like grouped notifications. ✕ goes back to the keys.
struct ResultsView: View {
    @ObservedObject var model: PanelModel

    private var title: String {
        if !model.series.isEmpty { return "Series · \(model.seriesIndex + 1) of \(model.series.count) sent" }
        return model.fromShortcut ? "From your screenshot · tap one to put it in" : "In your style · tap one to put it in"
    }

    var body: some View {
        VStack(spacing: 4) {
            HStack(spacing: 6) {
                Image(systemName: model.series.isEmpty ? (model.fromShortcut ? "camera.viewfinder" : "sparkles")
                                                       : "square.stack.fill")
                    .font(.caption.weight(.bold))
                Text(title)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.85)
                if !model.series.isEmpty {
                    SeriesProgress(count: model.series.count, sent: model.seriesIndex + 1)
                }
                Spacer(minLength: 0)
                Button { model.closeResults() } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title3)
                        .symbolRenderingMode(.hierarchical)
                        .frame(width: 36, height: 30)
                        .contentShape(.rect)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Back to the keys")
            }
            .foregroundStyle(.secondary)
            .padding(.leading, 6)
            ScrollView {
                VStack(spacing: 8) {
                    if !model.series.isEmpty {
                        NextPartCard(model: model)
                    } else {
                        ForEach(model.options) { option in
                            if option.parts.count > 1 {
                                SeriesStack(parts: option.parts, label: option.label) { model.insert(option) }
                            } else {
                                OptionCard(option: option) { model.insert(option) }
                            }
                        }
                    }
                }
                .padding(.horizontal, 3)
                .padding(.top, 2)
                .padding(.bottom, 8)
            }
            .scrollIndicators(.hidden)
        }
        .padding(.horizontal, 3)
        .padding(.top, 4)
    }
}

/// How far a series has been sent: one dot per message.
struct SeriesProgress: View {
    let count: Int
    let sent: Int

    var body: some View {
        HStack(spacing: 3) {
            ForEach(0..<max(count, 0), id: \.self) { index in
                Capsule()
                    .fill(index < sent ? Color.primary.opacity(0.7) : Color.secondary.opacity(0.3))
                    .frame(width: index < sent ? 12 : 6, height: 4)
            }
        }
    }
}

/// A result card: the letter-key color with the stock 1 pt key shadow, so it sits on the backdrop like a key.
struct ResultCard: View {
    var depth = 0  // cards further back in a stack are fainter

    @Environment(\.colorScheme) private var scheme

    var body: some View {
        RoundedRectangle(cornerRadius: KeyTheme.card, style: .continuous)
            .fill(KeyTheme.cardFill(scheme))
            .shadow(color: KeyTheme.keyShadow(scheme), radius: 0, x: 0, y: 1)
            .opacity(depth == 0 ? 1 : (depth == 1 ? 0.7 : 0.45))
    }
}

/// One variant as a tappable card; tap puts it in the field.
struct OptionCard: View {
    let option: PanelOption
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 8) {
                VStack(alignment: .leading, spacing: 3) {
                    if let label = option.label {
                        Text(label.replacingOccurrences(of: "_", with: " ").uppercased())
                            .font(.system(size: 9, weight: .bold))
                            .tracking(0.6)
                            .foregroundStyle(.secondary)
                    }
                    Text(option.text)
                        .foregroundStyle(.primary)
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Image(systemName: "arrow.down.left")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(.secondary)
                    .padding(.top, 3)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 9)
            .background { ResultCard() }
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
    }
}

/// The first message on top, the rest peeking out underneath ("+2"); tap the header to see them all.
struct SeriesStack: View {
    let parts: [String]
    let label: String?
    let action: () -> Void

    @State private var expanded = false
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Button { withAnimation(.snappy) { expanded.toggle() } } label: {
                HStack(spacing: 4) {
                    Image(systemName: "square.stack")
                    Text("\(parts.count) messages\(label.map { " · \($0.replacingOccurrences(of: "_", with: " "))" } ?? "")")
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                }
                .font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
            Button(action: action) {
                if expanded {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(Array(parts.enumerated()), id: \.offset) { _, part in
                            bubble(part, depth: 0)
                        }
                    }
                } else {
                    ZStack(alignment: .top) {
                        ForEach(Array(parts.prefix(3).enumerated().reversed()), id: \.offset) { index, part in
                            bubble(index == 0 ? part : " ", depth: index)
                                .scaleEffect(x: 1 - CGFloat(index) * 0.05, anchor: .top)
                                .offset(y: CGFloat(index) * 6)
                        }
                    }
                    .padding(.bottom, CGFloat(min(parts.count, 3) - 1) * 6)
                    .overlay(alignment: .bottomTrailing) {
                        Text("+\(parts.count - 1)")
                            .font(.caption2.weight(.heavy))
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 7).padding(.vertical, 2)
                            .background(KeyTheme.chipFill(scheme), in: .capsule)
                            .offset(x: -6, y: -2)
                    }
                }
            }
            .buttonStyle(.plain)
        }
    }

    /// A message card; the ones further back are fainter, so the stack has depth.
    private func bubble(_ text: String, depth: Int) -> some View {
        Text(text)
            .foregroundStyle(.primary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .lineLimit(2)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background { ResultCard(depth: depth) }
    }
}

/// While a series is being sent: send the part in the field, then tap here for the next one.
struct NextPartCard: View {
    @ObservedObject var model: PanelModel

    var body: some View {
        let next = model.seriesIndex + 1 < model.series.count ? model.series[model.seriesIndex + 1] : nil
        VStack(alignment: .leading, spacing: 6) {
            Label("Send this one, then tap the next", systemImage: "paperplane")
                .font(.caption).foregroundStyle(.secondary)
            if let next {
                Button(action: model.insertNextPart) {
                    HStack(alignment: .top, spacing: 8) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("NEXT")
                                .font(.system(size: 9, weight: .bold))
                                .tracking(0.6)
                                .foregroundStyle(.secondary)
                            Text(next).foregroundStyle(.primary)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        Image(systemName: "arrow.down.left")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.secondary)
                            .padding(.top, 2)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 9)
                    .background { ResultCard() }
                    .contentShape(.rect)
                }
                .buttonStyle(.plain)
            }
            ForEach(Array(model.series.enumerated()).dropFirst(model.seriesIndex + 2), id: \.offset) { _, part in
                Text(part).font(.footnote).foregroundStyle(.secondary).lineLimit(1).padding(.horizontal, 10)
            }
        }
    }
}
