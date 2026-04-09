import SwiftUI
import Charts

struct CostsTabView: View {
    @StateObject private var vm = CostsViewModel()

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(spacing: 16) {
                HStack {
                    Text("Costs")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundStyle(ReefGradients.accent)
                    Spacer()
                }
                .padding(.horizontal, ReefTheme.screenPadding)
                .appearAnimated()

                if vm.isLoading {
                    LoadingView().frame(minHeight: 300)
                } else {
                    VStack(spacing: 16) {
                        // Wizard prompt
                        if !vm.wizardCompleted {
                            ReefCard {
                                VStack(spacing: 12) {
                                    Image(systemName: "wand.and.stars")
                                        .font(.system(size: 32))
                                        .foregroundColor(.accent)
                                    Text("Set Up Cost Tracking")
                                        .font(.headline)
                                        .foregroundColor(.textPrimary)
                                    Text("Answer a few questions about your equipment and we'll calculate your estimated monthly costs.")
                                        .font(.subheadline)
                                        .foregroundColor(.textSecondary)
                                        .multilineTextAlignment(.center)
                                    ReefButton("Start Cost Wizard") {
                                        vm.showWizard = true
                                    }
                                }
                            }
                            .padding(.horizontal, ReefTheme.screenPadding)
                        }

                        // Monthly total
                        if vm.wizardCompleted {
                            ReefCard {
                                VStack(spacing: 4) {
                                    Text("ESTIMATED MONTHLY COST")
                                        .font(.caption)
                                        .foregroundColor(.textSecondary)
                                    Text(String(format: "$%.2f", vm.monthlyTotal))
                                        .font(.system(size: 36, weight: .bold))
                                        .foregroundColor(.accent)
                                    Text("recurring costs only")
                                        .font(.caption2)
                                        .foregroundColor(.textSecondary)
                                }
                                .frame(maxWidth: .infinity)
                            }
                            .padding(.horizontal, ReefTheme.screenPadding)
                        }

                        // Tab selector
                        Picker("View", selection: $vm.selectedTab) {
                            Text("Monthly").tag(0)
                            Text("Purchases").tag(1)
                        }
                        .pickerStyle(.segmented)
                        .padding(.horizontal, ReefTheme.screenPadding)

                        if vm.selectedTab == 0 {
                            MonthlyView(vm: vm)
                        } else {
                            PurchasesView(vm: vm)
                        }
                    }
                }
            }
            .padding(.top, 8)
        }
        .background(Color.bgDeep)
        .refreshable { await vm.load() }
        .sheet(isPresented: $vm.showAddPurchase) {
            AddPurchaseSheet(vm: vm)
        }
        .fullScreenCover(isPresented: $vm.showWizard) {
            CostWizardView {
                Task { await vm.load() }
            }
        }
        .task { await vm.load() }
    }
}

// MARK: - Monthly View

struct MonthlyView: View {
    @ObservedObject var vm: CostsViewModel

    var body: some View {
        VStack(spacing: 12) {
            if vm.recurringCosts.isEmpty {
                EmptyStateView(icon: "dollarsign.circle", title: "No recurring costs", subtitle: "Complete the cost wizard to get estimates")
            } else {
                // Donut chart
                if #available(iOS 17.0, *) {
                    Chart(vm.recurringCosts) { cost in
                        SectorMark(
                            angle: .value("Amount", cost.monthlyAmount ?? 0),
                            innerRadius: .ratio(0.6)
                        )
                        .foregroundStyle(by: .value("Category", cost.category ?? "Other"))
                    }
                    .chartLegend(position: .bottom, spacing: 12)
                    .frame(height: 200)
                    .padding(.horizontal, ReefTheme.screenPadding)
                } else {
                    // Fallback: bar chart for iOS 16
                    Chart(vm.recurringCosts) { cost in
                        BarMark(
                            x: .value("Amount", cost.monthlyAmount ?? 0),
                            y: .value("Category", cost.category ?? "Other")
                        )
                        .foregroundStyle(Color.accent)
                    }
                    .frame(height: 200)
                    .padding(.horizontal, ReefTheme.screenPadding)
                }

                // Breakdown list
                VStack(alignment: .leading, spacing: 4) {
                    Text("BREAKDOWN")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundColor(.textSecondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, ReefTheme.screenPadding)

                ForEach(vm.recurringCosts) { cost in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(cost.category ?? "Other")
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundColor(.textPrimary)
                            Text(cost.description ?? "")
                                .font(.caption2)
                                .foregroundColor(.textSecondary)
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: 2) {
                            Text(String(format: "$%.2f", cost.monthlyAmount ?? 0))
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(.textPrimary)
                            Text(cost.source == "calculated" ? "ESTIMATED" : "ACTUAL")
                                .font(.caption2)
                                .fontWeight(.bold)
                                .foregroundColor(cost.source == "calculated" ? .accent : .success)
                        }
                    }
                    .padding(12)
                    .background(Color.cardSolid)
                    .cornerRadius(ReefTheme.smallCornerRadius)
                    .padding(.horizontal, ReefTheme.screenPadding)
                }

                // Re-run Wizard button
                if vm.wizardCompleted {
                    Button {
                        Haptics.light()
                        vm.showWizard = true
                    } label: {
                        HStack {
                            Image(systemName: "arrow.clockwise")
                            Text("Re-run Wizard")
                        }
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.accent)
                        .frame(maxWidth: .infinity)
                        .padding(14)
                        .background(Color.accent.opacity(0.08))
                        .cornerRadius(ReefTheme.smallCornerRadius)
                        .overlay(
                            RoundedRectangle(cornerRadius: ReefTheme.smallCornerRadius)
                                .stroke(Color.accent.opacity(0.2), lineWidth: 1)
                        )
                    }
                    .pressable()
                    .padding(.horizontal, ReefTheme.screenPadding)
                }
            }
        }
    }
}

// MARK: - Purchases View

struct PurchasesView: View {
    @ObservedObject var vm: CostsViewModel

    var body: some View {
        VStack(spacing: 12) {
            Button {
                vm.showAddPurchase = true
            } label: {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Add Purchase")
                }
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(.accent)
                .frame(maxWidth: .infinity)
                .padding(12)
                .background(Color.accent.opacity(0.1))
                .cornerRadius(ReefTheme.smallCornerRadius)
            }
            .padding(.horizontal, ReefTheme.screenPadding)

            if vm.purchases.isEmpty {
                EmptyStateView(icon: "cart", title: "No purchases yet")
            } else {
                ForEach(vm.purchases) { entry in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(entry.description ?? entry.category ?? "")
                                .font(.subheadline)
                                .foregroundColor(.textPrimary)
                            Text(entry.purchaseDate ?? "")
                                .font(.caption2)
                                .foregroundColor(.textSecondary)
                        }
                        Spacer()
                        Text(String(format: "$%.2f", entry.amount ?? 0))
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(.textPrimary)

                        Button {
                            Task { await vm.deletePurchase(entry) }
                        } label: {
                            Image(systemName: "trash")
                                .font(.caption)
                                .foregroundColor(.danger)
                        }
                    }
                    .padding(12)
                    .background(Color.cardSolid)
                    .cornerRadius(ReefTheme.smallCornerRadius)
                    .padding(.horizontal, ReefTheme.screenPadding)
                }
            }
        }
    }
}

// MARK: - Add Purchase Sheet

struct AddPurchaseSheet: View {
    @ObservedObject var vm: CostsViewModel
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationView {
            ZStack {
                Color.bgDeep.ignoresSafeArea()
                VStack(spacing: 16) {
                    // Category pills
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(vm.purchaseCategories, id: \.self) { cat in
                                Button {
                                    vm.newCategory = cat
                                } label: {
                                    Text(cat)
                                        .font(.caption)
                                        .foregroundColor(vm.newCategory == cat ? .white : .textPrimary)
                                        .padding(.horizontal, 12)
                                        .padding(.vertical, 8)
                                        .background(vm.newCategory == cat ? Color.accent : Color.cardSolid)
                                        .cornerRadius(ReefTheme.pillCornerRadius)
                                }
                            }
                        }
                    }

                    ReefTextField(placeholder: "Description (optional)", text: $vm.newDescription)

                    ReefTextField(placeholder: "Amount", text: $vm.newAmount, keyboardType: .decimalPad)

                    DatePicker("Date", selection: $vm.newDate, displayedComponents: .date)
                        .foregroundColor(.textPrimary)
                        .colorScheme(.dark)

                    ReefButton("Add Purchase") {
                        Task { await vm.addPurchase() }
                    }

                    Spacer()
                }
                .padding(ReefTheme.screenPadding)
            }
            .navigationTitle("Add Purchase")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(.accent)
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}
