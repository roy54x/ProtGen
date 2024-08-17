import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset


class CustomDataset(Dataset):
    def __init__(self, dataframe, strategy):
        self.dataframe = dataframe
        self.strategy = strategy

    def __len__(self):
        return len(self.dataframe)

    def __getitem__(self, idx):
        row = self.dataframe.iloc[idx]
        inputs = self.strategy.load_inputs(row)
        ground_truth = self.strategy.get_ground_truth(row)
        return inputs, ground_truth


class Trainer:
    def __init__(self, dataframe, strategy, batch_size=32, test_size=0.2):
        train_df, test_df = train_test_split(dataframe, test_size=test_size, random_state=42, shuffle=False)
        self.train_loader = DataLoader(CustomDataset(train_df, strategy), batch_size=batch_size, shuffle=True)
        self.test_loader = DataLoader(CustomDataset(test_df, strategy), batch_size=batch_size, shuffle=False)
        self.strategy = strategy

    def train(self, optimizer, epochs=10):
        self.strategy.train()
        for epoch in range(epochs):
            total_train_loss = 0
            for inputs, ground_truth in self.train_loader:
                optimizer.zero_grad()
                outputs = self.strategy(inputs)
                loss = self.strategy.compute_loss(outputs, ground_truth)
                loss.backward()
                optimizer.step()
                total_train_loss += loss.item()

            print(f'Epoch {epoch + 1}, Training Loss: {total_train_loss}')

            # Evaluate on test data
            self.strategy.eval()
            total_test_loss = 0
            with torch.no_grad():
                for inputs, ground_truth in self.test_loader:
                    outputs = self.strategy(inputs)
                    loss = self.strategy.compute_loss(outputs, ground_truth)
                    total_test_loss += loss.item()
            print(f'Epoch {epoch + 1}, Test Loss: {total_test_loss}')
            self.strategy.train()  # Switch back to training mode