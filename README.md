# WSI extractor

Tiling patches or generate patches of whole slide image based on Openslide


## Basic Functions
- Tiling patches and saving them to local disk
- Generate patch generator for testing of WSIs 
 
## Usage  

- First assign the slide_folder(will findslides in subfolder(s)) and save_folder.
``` python
slide_folder = os.path.join(os.curdir, 'data', 'slide')
save_folder = os.path.join(os.curdir, 'data', 'patch')
```

- For tiling patches and saving them to disks
``` python
TileSaving(slide_folder, save_folder, n_procs=4, target_size=512, ds_rate=0, black_thresh=50).tiling()
```
- For get patch generation (using in the inference code) 

``` python
loaderuence = TestDataGenerator(slide_folder).get_patch_generator(mode='sequence')
for patch_gen, idx in loaderuence:
    for patch, c, r in patch_gen:
        if patch == -1:
            # patch is black
            pass
        elif patch == -2:
            # patch is blank
            pass
        else:
            # patch is valid
            pass

loader_randomly = TestDataGenerator(slide_folder).get_patch_generator(mode='random')
for patch_gen, idx in loader_randomly:
    for patch, c, r in patch_gen:
        if patch == -1:
            # patch is black
            pass
        elif patch == -2:
            # patch is blank
            pass
        else:
            # patch is valid
            pass
```
 
