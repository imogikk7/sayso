import SwiftUI

/// ✨ results in place of the keys: each variant a card; a series is a stack of messages like grouped notifications.
struct ResultsView: View {
    @ObservedObject var model: PanelModel

    var body: some View {
        VStack(spacing: 6) {
            HStack {
                Text(model.series.isEmpty ? "In your style" : "Series · \(model.seriesIndex + 1) of \(model.series.count) sent")
                    .font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                Spacer()
                Button { model.closeResults() } label: { Image(systemName: "xmark.circle.fill").font(.title3) }
                    .foregroundStyle(.secondary)
            }
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
            }
        }
        .padding(.horizontal, 8)
    }
}

struct OptionCard: View {
    let option: PanelOption
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 8) {
                if let label = option.label {
                    Text(label.replacingOccurrences(of: "_", with: " ")).font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
                        .frame(width: 52, alignment: .leading)
                }
                Text(option.text).frame(maxWidth: .infinity, alignment: .leading).multilineTextAlignment(.leading)
                Image(systemName: "arrow.down.left").foregroundStyle(.secondary)
            }
            .padding(10)
            .background(Color(.systemBackground), in: .rect(cornerRadius: 12))
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
                        ForEach(Array(parts.enumerated()), id: \.offset) { _, part in bubble(part) }
                    }
                } else {
                    ZStack(alignment: .top) {
                        ForEach(Array(parts.prefix(3).enumerated().reversed()), id: \.offset) { index, part in
                            bubble(index == 0 ? part : " ")
                                .scaleEffect(x: 1 - CGFloat(index) * 0.05, anchor: .top)
                                .offset(y: CGFloat(index) * 6)
                                .opacity(index == 0 ? 1 : 0.7)
                        }
                    }
                    .padding(.bottom, CGFloat(min(parts.count, 3) - 1) * 6)
                    .overlay(alignment: .bottomTrailing) {
                        Text("+\(parts.count - 1)").font(.caption2.weight(.bold)).foregroundStyle(.secondary).padding(6)
                    }
                }
            }
            .buttonStyle(.plain)
        }
    }

    private func bubble(_ text: String) -> some View {
        Text(text)
            .frame(maxWidth: .infinity, alignment: .leading)
            .lineLimit(2)
            .padding(10)
            .background(Color(.systemBackground), in: .rect(cornerRadius: 12))
            .shadow(color: .black.opacity(0.08), radius: 2, y: 1)
    }
}

/// While a series is being sent: send the part in the field, then tap here for the next one.
struct NextPartCard: View {
    @ObservedObject var model: PanelModel

    var body: some View {
        let next = model.seriesIndex + 1 < model.series.count ? model.series[model.seriesIndex + 1] : nil
        VStack(alignment: .leading, spacing: 6) {
            Text("Send this one, then tap the next").font(.caption).foregroundStyle(.secondary)
            if let next {
                Button(action: model.insertNextPart) {
                    HStack {
                        Text("Next: \(next)").frame(maxWidth: .infinity, alignment: .leading)
                        Image(systemName: "arrow.down.left")
                    }
                    .padding(10)
                    .background(Color(.systemBackground), in: .rect(cornerRadius: 12))
                }
                .buttonStyle(.plain)
            }
            ForEach(Array(model.series.enumerated()).dropFirst(model.seriesIndex + 2), id: \.offset) { _, part in
                Text(part).font(.footnote).foregroundStyle(.secondary).lineLimit(1).padding(.horizontal, 10)
            }
        }
    }
}
