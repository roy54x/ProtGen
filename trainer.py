import os
from datetime import datetime

import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from torch import optim
from torch.utils.data import DataLoader, Dataset

from strategies.sequence_to_binding_sequence import SequenceDiffusionModel
from utils.constants import MIN_SIZE, MAIN_DIR
from strategies.sequence_to_contact_map import SequenceToContactMap


class CustomDataset(Dataset):
    def __init__(self, dataframe, strategy, dataset_name):
        self.dataframe = dataframe
        self.strategy = strategy
        print(f"number of samples in the {dataset_name} set are: {len(self.dataframe)}")

    def __len__(self):
        return len(self.dataframe)

    def __getitem__(self, idx):
        row = self.dataframe.iloc[idx]
        inputs, ground_truth = self.strategy.load_inputs_and_ground_truth(row)
        return inputs, ground_truth


class Trainer:
    def __init__(self, dataframe, strategy, batch_size=32, test_size=0.2):
        dataframe = dataframe[dataframe['sequence'].apply(lambda seq: len(seq) >= MIN_SIZE)]
        train_df, test_df = train_test_split(dataframe, test_size=test_size, random_state=42, shuffle=False)
        self.train_loader = DataLoader(CustomDataset(train_df, strategy, "train"), batch_size=batch_size, shuffle=True)
        self.test_loader = DataLoader(CustomDataset(test_df, strategy, "test"), batch_size=batch_size, shuffle=False)
        self.strategy = strategy
        self.optimizer = optim.Adam(strategy.parameters(), lr=0.001)
        self.best_test_loss = float('inf')
        print(f'Number of trainable parameters: '
              f'{sum(p.numel() for p in self.strategy.parameters() if p.requires_grad)}')

    def train(self, epochs=10):
        self.strategy.train()
        for epoch in range(epochs):
            total_train_loss = 0
            total_train_samples = 0
            batch_count = 0

            for inputs, ground_truth in self.train_loader:
                self.optimizer.zero_grad()
                outputs = self.strategy(inputs)
                loss = self.strategy.compute_loss(outputs, ground_truth)
                loss.backward()
                self.optimizer.step()
                total_train_loss += loss.item()
                total_train_samples += len(inputs)
                batch_count += 1

                # Print training loss every 100 batches
                if batch_count % 100 == 0:
                    avg_train_loss = total_train_loss / total_train_samples
                    print(f'Epoch {epoch + 1}, Batch {batch_count}, Training Loss: {avg_train_loss}')

            print(f'Epoch {epoch + 1}, Training Loss: {total_train_loss / total_train_samples}')

            # Evaluate on test data
            self.strategy.eval()
            total_test_loss = 0
            total_test_samples = 0
            with torch.no_grad():
                for inputs, ground_truth in self.test_loader:
                    outputs = self.strategy(inputs)
                    loss = self.strategy.compute_loss(outputs, ground_truth)
                    total_test_loss += loss.item()
                    total_test_samples += len(inputs)

            average_test_loss = total_test_loss / total_test_samples
            print(f'Epoch {epoch + 1}, Test Loss: {average_test_loss}')

            # Save the model if the test loss is the best seen so far
            if average_test_loss < self.best_test_loss:
                self.best_test_loss = average_test_loss
                self.save_model()

            self.strategy.train()  # Switch back to training mode

    def save_model(self):
        # Create the directory name from strategy and date
        directory = os.path.join(MAIN_DIR, "models", self.strategy.__class__.__name__,
                                 datetime.now().strftime("%Y%m%d"))

        if not os.path.exists(directory):
            os.makedirs(directory)

        model_path = os.path.join(directory, 'best_model.pth')
        torch.save(self.strategy.state_dict(), model_path)
        print(f'Model saved at {model_path}')


if __name__ == '__main__':
    #dataframe = pd.read_json(os.path.join(MAIN_DIR,"PDB\pdb_df_100.json"))
    #strategy = SequenceToContactMap()
    dataframe = pd.read_csv(os.path.join(MAIN_DIR,"UniProt\\uniprot_df.csv"))
    strategy = SequenceDiffusionModel()
    trainer = Trainer(dataframe, strategy, batch_size=16, test_size=0.2)
    trainer.train(epochs=100)
