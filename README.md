# WEBUI for e621 Posts Downloader
![visitor badge](https://visitor-badge.glitch.me/badge?page_id=x-CK-x.pikaft-e621-posts-downloader)

##### Original Backend development project: https://github.com/pikaflufftuft/pikaft-e621-posts-downloader

## Features

- User friendly UI
- Easy to load, edit, & create new json configs
- Advanced configuration tabs
- Easy to run directly from the UI
- Easy to run multiple configs in batch runs

## Features (Coming Soon)

- Gallery preview w/ search capability
- Easy to use Tag Editor
- Tag statistics tab
- Tag auto-completion

## Requirements
python 3.8+

clone repository
```
git clone https://github.com/x-CK-x/pikaft-e621-posts-downloader.git
```
```
cd pikaft-e621-posts-downloader
pip install -r requirements.txt
```

#### aria2
This downloader uses aria2 for fast downloading.
```
sudo apt-get install aria2
```
For Windows, install the aria2 build https://github.com/aria2/aria2/releases/ Add aria2 in your evironment variable paths

## How to use

#### Run the Web-User Interface
```
python webui.py
```

## Additional Information

#### File and Folder Paths
Whether it's a file or a folder path, you can specify either a relative path or an absolute path. Each parameter that is a relative path uses the specified parent folder in each batch accordingly.

##### Default folder directory tree
```
base_folder/
├─ batch_folder/
│  ├─ downloaded_posts_folder/
│  │  ├─ png_folder/
│  │  ├─ jpg_folder/
│  │  ├─ gif_folder/
│  │  ├─ webm_folder/
│  │  ├─ swf_folder/
│  ├─ resized_img_folder/
│  ├─ tag_count_list_folder/
│  │  ├─ tags.csv
│  │  ├─ tag_category.csv
│  ├─ save_searched_list_path.txt
```
Any file path parameter that are empty will use the default path.

Files/folders that use the same path are merged, not overwritten. For example, using the same path for save_searched_list_path at every batch will result in a combined searched list of every batch in one .txt file.

#### e621 tag categories:    
* general (`anthro`, `female`, `solo`, ...)
* artist (`tom_fischbach`, `unknown_artist`, ...)
* copyright (`nintendo`, `pokemon`, `disney`, ...)
* character (`loona_(helluva_boss)`, `legoshi_(beastars)`, ...)
* species (`canine`, `fox`, `dragon`, ...)
* invalid (`spooky_(disambiguation)`, ...)
* meta (`hi_res`, `digital_media_(artwork)`, ...)
* lore (`trans_(lore)`, `male_(lore)`, ...)
* rating (`explicit`, `questionable`, `safe`) (rating tags are techincally not e621 tags)

### Notes
* When downloading, if the file already exists, it is skipped, unless, the file exists but was modified, it will download and the modified file will be renamed. Hence, I recommend not setting `delete_original` to `true` if you plan redownloading using the same destination folder.
* When resizing, when `resized_img_folder` uses a different folder from the source folder, if the file in the destination folder already exists, it is skipped. It does not check if the already existing file has the specified `min_short_side`.
* When running a new batch using the same save directories for tag files, tag count folders, and save_searched_list, tag files, tag count csvs, and save_searched_lists will be overwritten.

### Please see the original backend development project for more information: https://github.com/pikaflufftuft/pikaft-e621-posts-downloader

## License

MIT

## Usage conditions
By using this downloader, the user agrees that the author is not liable for any misuse of this downloader. This downloader is open-source and free to use.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
