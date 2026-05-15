import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors 
import seaborn as sns
import pandas as pd

class Visualizer:
    def __init__(self):
        self.result_path = None

    def set_result_path(self, result_path: str):
        self.result_path = result_path

    def write_matrix_img(self, matrix, name, **kwargs):
        if not self.result_path:
            raise ValueError('Result path is not set. Please set the result path')
        
        if matrix is None:
            return
     # Manage kwargs
        row_labels = kwargs.get('row_labels')
        column_labels = kwargs.get('column_labels')
        cbar = kwargs.get('cbar', False)
        cmap = kwargs.get('cmap', 'viridis')
        linewidth = kwargs.get('linewidth', 0)
        title = kwargs.get('title', None)
        colors_list = kwargs.get('colors_list', None)
        min_val = kwargs.get('min_val', None)
        max_val = kwargs.get('max_val', None)
        color_labels = kwargs.get('color_labels', None)  # Labels for color bar
        x_label = kwargs.get('x_label', None)
        y_label = kwargs.get('y_label', None)

        # If a custom color map is provided via colors_list
        if colors_list:
            cmap = colors.ListedColormap(colors_list)
        elif cmap:
            cmap = cmap
        else:
            cmap = 'viridis'

        # Create a Seaborn heatmap
        plt.figure(figsize=(10, 8))  # Adjust the figure size if necessary
        ax = sns.heatmap(matrix,
                         cmap=cmap,
                         linewidths=linewidth,  # Control the thickness of the gridlines
                         linecolor='gray',      # Color of the gridlines
                         xticklabels=column_labels,
                         yticklabels=row_labels,
                         cbar=cbar,             # Display colorbar if required
                         vmin=min_val,
                         vmax=max_val,
                         square=True,
                         cbar_kws={'shrink': 0.5})           # Ensure square cells

        # Set title and labels if provided
        if title:
            ax.set_title(title)
        if x_label:
            ax.set_xlabel(x_label)
        if y_label:
            ax.set_ylabel(y_label)
        
        if len(column_labels) == 0 or len(row_labels) == 0:
            return

        x_fontsize = min(10, 300 // len(column_labels))
        y_fontsize = min(10, 300 // len(row_labels))
        ax.set_xticklabels(column_labels, fontsize=x_fontsize, rotation=90)
        ax.set_yticklabels(row_labels, fontsize=y_fontsize)

        # Add labels to the color bar if cbar is True
        if cbar and color_labels and min_val is not None and max_val is not None:
            # Get color bar object
            cbar_obj = ax.collections[0].colorbar

            # Create tick positions (equally spaced)
            ticks = np.linspace(min_val, max_val, len(color_labels))

            # Set the ticks and labels on the color bar
            cbar_obj.set_ticks(ticks)
            cbar_obj.set_ticklabels(color_labels)

            # Adjust the colorbar label size (max 10 or 300/len(color_labels))
            label_fontsize = min(10, 300 // len(color_labels))
            cbar_obj.ax.tick_params(labelsize=label_fontsize)
        
        

        # Save the plot as an SVG
        plt.savefig(self.result_path + '/' + name + '.pdf', format='pdf', bbox_inches='tight')
        plt.clf()  # Clear the figure for the next plot


    def write_text_file(self, name, text=None, texts=None, preface=None):
        if not self.result_path:
            raise ValueError('Result path is not set. Please set the result path')
        if text:
            with open(self.result_path + '/' + name + '.txt', 'w') as file:
                if preface:
                    file.write(preface + '\n')
                file.write(text + '\n')

        elif texts:
            with open(self.result_path + '/' + name + '.txt', 'w') as file:
                if preface:
                    file.write(preface + '\n')
                for text in texts:
                    file.write(text + '\n')
    
    # dict_list is a list of dicts where the "key" is the name of a columns and the "value" is the value for that row
    # meaning every dict represents a row in the dataframe
    def write_csv_file(self, name, dict_list):
        df = pd.DataFrame(dict_list)
        if not df.empty:
            df.to_csv(self.result_path+"/"+name+".csv", sep=",")