import gradio as gr
import os
import json
import copy
import multiprocessing as mp
import subprocess as sub
import glob

import e621_batch_downloader

'''
##################################################################################################################################
###################################################     HELPER FUNCTIONS     #####################################################
##################################################################################################################################
'''

def verbose_print(text):
    print(f"{text}")

def load_session_config(f_name):
    session_config = None
    file_exists = os.path.exists(f_name)
    if not file_exists: # create the file
        with open(f_name, 'w') as f:
            f.close()
    else: # load the file
        data_flag = True # detects if the file is empty
        with open(f_name, 'r') as json_file:
            lines = json_file.readlines()
            if len(lines) == 0 or len(lines[0].replace(' ', '')) == 0:
                data_flag = False
            json_file.close()

        if data_flag: # data present
            with open(f_name) as json_file:
                data = json.load(json_file)

                temp_config = [dictionary for dictionary in data]
                if len(temp_config) > 0:
                    session_config = data
                else:
                    session_config = {}
                json_file.close()
    return session_config

def grab_pre_selected(settings, all_checkboxes):
    pre_selected_checkboxes = []
    for key in all_checkboxes:
        if settings[key]:
            pre_selected_checkboxes.append(key)
    return pre_selected_checkboxes

def update_JSON(settings, temp_config_name):
    temp = copy.deepcopy(settings)
    for entry in temp:
        verbose_print(f"{entry}:\t{settings[entry]}")

    with open(temp_config_name, "w") as f:
        json.dump(temp, indent=4, fp=f)
    f.close()
    verbose_print("="*42)

def create_dirs(arb_path):
    if not os.path.exists(arb_path):
        os.makedirs(arb_path)

def execute(cmd):
    popen = sub.Popen(cmd, stdout=sub.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise sub.CalledProcessError(return_code, cmd)

def get_list(arb_string, delimeter):
    return arb_string.split(delimeter)

def get_string(arb_list, delimeter):
    return delimeter.join(arb_list)

def from_padded(line):
    if len(line) > 1:# check for padded-0
        if int(line[0]) == 0:# remove the 0, cast to int, return
            return int(line[-1])
    return int(line)

def to_padded(num):
    return f"{num:02}"

def is_windows():
    return os.name == 'nt'

def parse_files_all_tags(file_list):
    all_tags_all_files = {}
    temp = '\\' if is_windows() else '/'
    for single_file in file_list:
        all_tags = []
        img_id = single_file.split(temp)[-1].split(".")[0]
        # verbose_print(f"single_file:\t\t{single_file}")
        with open(single_file, 'r', encoding='utf-8') as read_file:
            while True:
                line = read_file.readline()
                if not line:
                    break

                line = line.replace(" ", "")
                length = len(line.split(","))

                if length > 3:  # assume everything on one line
                    tags = line.split(",")
                    for tag in tags:
                        all_tags.append(tag)
                else:  # assume cascaded tags
                    tag = line.split(",")[0]
                    all_tags.append(tag)
            read_file.close()
            all_tags_all_files[img_id] = all_tags
    return all_tags_all_files.copy()


def parse_csv_all_tags(csv_file_path):
    # verbose_print(f"single_file:\t\t{csv_file_path}")
    temp_dict = {}
    counter = 0
    with open(csv_file_path, 'r', encoding='utf-8') as read_file:
        while True:
            line = read_file.readline()
            if not line:
                break
            if counter > 0:
                line = line.replace(" ", "")
                key = line.split(',')[0]
                value = line.split(',')[-1]
                temp_dict[key] = int(value.strip())
            counter += 1
        read_file.close()
    return temp_dict.copy()

'''
##################################################################################################################################
#############################################     PRIMARY VARIABLE DECLARATIONS     ##############################################
##################################################################################################################################
'''

# set local path
cwd = os.getcwd()

# options
img_extensions = ["png", "jpg", "same_as_original"]
method_tag_files_opts = ["relocate", "copy"]
collect_checkboxes = ["include_tag_file", "include_explicit_tag", "include_questionable_tag", "include_safe_tag",
                      "include_png", "include_jpg", "include_gif", "include_webm", "include_swf", "include_explicit",
                      "include_questionable", "include_safe"]
download_checkboxes = ["skip_post_download", "reorder_tags", "replace_underscores", "remove_parentheses", "do_sort"]
resize_checkboxes = ["skip_resize", "delete_original"]
file_extn_list = ["png", "jpg", "gif"]

### assume settings.json at the root dir of repo

# session config
global config_name
config_name = "settings.json"

global is_csv_loaded
is_csv_loaded = False
global artist_csv_dict, character_csv_dict, species_csv_dict, general_csv_dict, meta_csv_dict, rating_csv_dict, tags_csv_dict # load on dropdown click - stats / radio click - gallery (always do BOOL check)
artist_csv_dict = {}
character_csv_dict = {}
species_csv_dict = {}
general_csv_dict = {}
meta_csv_dict = {}
rating_csv_dict = {}
tags_csv_dict = {}
# ignore the first line in the csv file
global selected_image_dict # set on every click ::  # id -> {categories: tag/s}, type -> string
selected_image_dict = None### key:category, value:tag_list
global all_images_dict # load on radio click - gallery (always do BOOL check)
all_images_dict = {}### add images by key:id, value:selected_image_dict

global settings_json
settings_json = load_session_config(os.path.join(cwd, config_name))

global required_tags_list
required_tags_list = get_list(settings_json["required_tags"], settings_json["tag_sep"])
for tag in required_tags_list:
    if len(tag) == 0:
        required_tags_list.remove(tag)

global blacklist_tags
blacklist_tags = get_list(settings_json["blacklist"], " | ")
for tag in blacklist_tags:
    if len(tag) == 0:
        blacklist_tags.remove(tag)

verbose_print(f"{settings_json}")
verbose_print(f"json key count: {len(settings_json)}")

# UPDATE json with new key, value pairs
if not "min_date" in settings_json:
    settings_json["min_year"] = 2000
elif isinstance(settings_json["min_date"], str) and "-" in settings_json["min_date"]:
    settings_json["min_year"] = int(settings_json["min_date"].split("-")[0])
else:
    settings_json["min_year"] = int(settings_json["min_date"])

if not "min_month" in settings_json:
    settings_json["min_month"] = 1
elif isinstance(settings_json["min_date"], str) and "-" in settings_json["min_date"]:
    settings_json["min_month"] = from_padded(settings_json["min_date"].split("-")[1])

if not "min_day" in settings_json:
    settings_json["min_day"] = 1
elif isinstance(settings_json["min_date"], str) and settings_json["min_date"].count("-") > 1:
    settings_json["min_day"] = from_padded(settings_json["min_date"].split("-")[-1])

update_JSON(settings_json, config_name)

'''
##################################################################################################################################
#################################################     COMPONENT/S FUNCTION/S     #################################################
##################################################################################################################################
'''


def reset_selected_img(img_id_textbox):
    # reset selected_img
    global selected_image_dict
    selected_image_dict = None

    # reset img_id_textbox
    img_id_textbox = gr.update(value="")

    # reset all checkboxgroup components
    img_artist_tag_checkbox_group = gr.update(choices=[])
    img_character_tag_checkbox_group = gr.update(choices=[])
    img_species_tag_checkbox_group = gr.update(choices=[])
    img_general_tag_checkbox_group = gr.update(choices=[])
    img_meta_tag_checkbox_group = gr.update(choices=[])
    img_rating_tag_checkbox_group = gr.update(choices=[])

    return img_id_textbox, img_artist_tag_checkbox_group, img_character_tag_checkbox_group, img_species_tag_checkbox_group, img_general_tag_checkbox_group, img_meta_tag_checkbox_group, img_rating_tag_checkbox_group

def config_save_button(batch_folder,resized_img_folder,tag_sep,tag_order_format,prepend_tags,append_tags,img_ext,
                              method_tag_files,min_score,min_fav_count,min_area,top_n,min_short_side,
                              skip_posts_file,skip_posts_type,
                       collect_from_listed_posts_file,collect_from_listed_posts_type,apply_filter_to_listed_posts,
                       save_searched_list_type,save_searched_list_path,downloaded_posts_folder,png_folder,jpg_folder,
                       webm_folder,gif_folder,swf_folder,save_filename_type,remove_tags_list,replace_tags_list,
                       tag_count_list_folder,min_month,min_day,min_year,collect_checkbox_group_var,download_checkbox_group_var,
                       resize_checkbox_group_var,create_new_config_checkbox,settings_path):
    global settings_json
    settings_json["batch_folder"] = str(batch_folder)
    settings_json["resized_img_folder"] = str(resized_img_folder)
    settings_json["tag_sep"] = str(tag_sep)
    settings_json["tag_order_format"] = str(tag_order_format)
    settings_json["prepend_tags"] = str(prepend_tags)
    settings_json["append_tags"] = str(append_tags)
    settings_json["img_ext"] = str(img_ext)
    settings_json["method_tag_files"] = str(method_tag_files)
    settings_json["min_score"] = int(min_score)
    settings_json["min_fav_count"] = int(min_fav_count)

    settings_json["min_year"] = int(min_year)
    settings_json["min_month"] = int(min_month)
    settings_json["min_day"] = int(min_day)

    settings_json["min_date"] = f"{int(min_year)}-{to_padded(int(min_month))}-{to_padded(int(min_day))}"

    settings_json["min_area"] = int(min_area)
    settings_json["top_n"] = int(top_n)
    settings_json["min_short_side"] = int(min_short_side)

    # COLLECT CheckBox Group
    for key in collect_checkboxes:
        if key in collect_checkbox_group_var:
            settings_json[key] = True
        else:
            settings_json[key] = False
    # DOWNLOAD CheckBox Group
    for key in download_checkboxes:
        if key in download_checkbox_group_var:
            settings_json[key] = True
        else:
            settings_json[key] = False
    # RESIZE CheckBox Group
    for key in resize_checkboxes:
        if key in resize_checkbox_group_var:
            settings_json[key] = True
        else:
            settings_json[key] = False

    settings_json["required_tags"] = get_string(required_tags_list, str(tag_sep))
    settings_json["blacklist"] = get_string(blacklist_tags, " | ")

    settings_json["skip_posts_file"] = str(skip_posts_file)
    settings_json["skip_posts_type"] = str(skip_posts_type)
    settings_json["collect_from_listed_posts_file"] = str(collect_from_listed_posts_file)
    settings_json["collect_from_listed_posts_type"] = str(collect_from_listed_posts_type)
    settings_json["apply_filter_to_listed_posts"] = bool(apply_filter_to_listed_posts)
    settings_json["save_searched_list_type"] = str(save_searched_list_type)
    settings_json["save_searched_list_path"] = str(save_searched_list_path)
    settings_json["downloaded_posts_folder"] = str(downloaded_posts_folder)
    settings_json["png_folder"] = str(png_folder)
    settings_json["jpg_folder"] = str(jpg_folder)
    settings_json["webm_folder"] = str(webm_folder)
    settings_json["gif_folder"] = str(gif_folder)
    settings_json["swf_folder"] = str(swf_folder)
    settings_json["save_filename_type"] = str(save_filename_type)
    settings_json["remove_tags_list"] = str(remove_tags_list)
    settings_json["replace_tags_list"] = str(replace_tags_list)
    settings_json["tag_count_list_folder"] = str(tag_count_list_folder)

    if create_new_config_checkbox: # if called from the "create new button" the True flag will always be passed to ensure this
        temp = '\\' if is_windows() else '/'
        global config_name
        if temp in settings_path:
            config_name = settings_path
        else:
            config_name = os.path.join(cwd, settings_path)

    if not config_name or len(config_name) == 0:
        raise ValueError('No Config Name Specified')

    # Update json
    update_JSON(settings_json, config_name)

    temp = '\\' if is_windows() else '/'
    return gr.update(choices=[(each_settings_file.split(temp)[-1]) for each_settings_file in glob.glob(os.path.join(cwd, f"*.json"))],
                                                                label='Select to Run', value=[])

def textbox_handler_required(tag_string_comp):
    temp_tags = None
    if settings_json["tag_sep"] in tag_string_comp:
        temp_tags = tag_string_comp.split(settings_json["tag_sep"])
    elif " | " in tag_string_comp:
        temp_tags = tag_string_comp.split(" | ")
    else:
        temp_tags = [tag_string_comp]

    for tag in temp_tags:
        if not tag in required_tags_list:
            required_tags_list.append(tag)
    return gr.update(lines=1, label='Press Enter to ADD tag/s (E.g. tag1    or    tag1, tag2, ..., etc.)', value=""), \
           gr.update(choices=required_tags_list, label='ALL Required Tags', value=[])

def textbox_handler_blacklist(tag_string_comp):
    temp_tags = None
    if settings_json["tag_sep"] in tag_string_comp:
        temp_tags = tag_string_comp.split(settings_json["tag_sep"])
    elif " | " in tag_string_comp:
        temp_tags = tag_string_comp.split(" | ")
    else:
        temp_tags = [tag_string_comp]

    for tag in temp_tags:
        if not tag in blacklist_tags:
            blacklist_tags.append(tag)
    return gr.update(lines=1, label='Press Enter to ADD tag/s (E.g. tag1    or    tag1, tag2, ..., etc.)', value=""), \
           gr.update(choices=blacklist_tags, label='ALL Blacklisted Tags', value=[])

def check_box_group_handler_required(check_box_group):
    for tag in check_box_group:
        required_tags_list.remove(tag)
    return gr.update(choices=required_tags_list, label='ALL Required Tags', value=[])

def check_box_group_handler_blacklist(check_box_group):
    for tag in check_box_group:
        blacklist_tags.remove(tag)
    return gr.update(choices=blacklist_tags, label='ALL Blacklisted Tags', value=[])

### file expects a format of 1 tag per line, with the tag being before the first comma
def parse_file_required(file_list):
    for single_file in file_list:
        with open(single_file.name, 'r', encoding='utf-8') as read_file:
            while True:
                line = read_file.readline()
                if not line:
                    break

                length = len(line.replace(" ", "").split(","))

                if length > 3: # assume everything on one line
                    tags = line.replace(" ", "").split(",")
                    for tag in tags:
                        if not tag in required_tags_list:
                            required_tags_list.append(tag)
                else: # assume cascaded tags
                    tag = line.replace(" ", "").split(",")[0]
                    if not tag in required_tags_list:
                        required_tags_list.append(tag)
            read_file.close()
    return gr.update(choices=required_tags_list, label='ALL Required Tags', value=[])

### file expects a format of 1 tag per line, with the tag being before the first comma
def parse_file_blacklist(file_list):
    for single_file in file_list:
        with open(single_file.name, 'r', encoding='utf-8') as read_file:
            while True:
                line = read_file.readline()
                if not line:
                    break

                length = len(line.replace(" ", "").split(","))

                if length > 3: # assume everything on one line
                    tags = line.replace(" ", "").split(",")
                    for tag in tags:
                        if not tag in blacklist_tags:
                            blacklist_tags.append(tag)
                else: # assume cascaded tags
                    tag = line.replace(" ", "").split(",")[0]
                    if not tag in blacklist_tags:
                        blacklist_tags.append(tag)
            read_file.close()
    return gr.update(choices=blacklist_tags, label='ALL Blacklisted Tags', value=[])

def make_run_visible():
    return gr.update(interactive=False, visible=True)

def run_script(basefolder='',settings_path=cwd,numcpu=-1,phaseperbatch=False,keepdb=False,cachepostsdb=False,postscsv='',tagscsv='',postsparquet='',tagsparquet='',aria2cpath=''):
    verbose_print(f"RUN COMMAND IS:\t{basefolder, settings_path, numcpu, phaseperbatch, postscsv, tagscsv, postsparquet, tagsparquet, keepdb, aria2cpath, cachepostsdb}")

    #### ADD A PIPE parameter that passes the connection to the other process
    global frontend_conn, backend_conn
    frontend_conn, backend_conn = mp.Pipe()
    global e6_downloader
    e6_downloader = mp.Process(target=e621_batch_downloader.E6_Downloader, args=(basefolder, settings_path, numcpu, phaseperbatch, postscsv, tagscsv, postsparquet, tagsparquet, keepdb, aria2cpath, cachepostsdb, backend_conn),)
    e6_downloader.start()

def run_script_batch(basefolder='',settings_path=cwd,numcpu=-1,phaseperbatch=False,keepdb=False,cachepostsdb=False,postscsv='',tagscsv='',postsparquet='',tagsparquet='',aria2cpath='',run_button_batch=None,progress=gr.Progress()):
    verbose_print(f"RUN COMMAND IS:\t{basefolder, settings_path, numcpu, phaseperbatch, postscsv, tagscsv, postsparquet, tagsparquet, keepdb, aria2cpath, cachepostsdb}")

    progress(0, desc="Starting...")
    for setting in progress.tqdm(run_button_batch, desc="Tracking Total Progress"):
        path = os.path.join(cwd, setting)
        if not ".json" in path:
            path += ".json"

        e6_downloader = e621_batch_downloader.E6_Downloader(basefolder, path, numcpu, phaseperbatch, postscsv, tagscsv, postsparquet, tagsparquet, keepdb, aria2cpath, cachepostsdb, None)
        del e6_downloader
    return gr.update(interactive=False, visible=False)

def data_collect(progress=gr.Progress()):
    # thread block and wait for response
    total = int(frontend_conn.recv())

    progress(0, desc="Starting...")
    for i in progress.tqdm(range(total), desc="Collecting"):
        _ = frontend_conn.recv()
    return gr.update(interactive=False, visible=False)

def data_download(progress=gr.Progress()):
    # thread block and wait for response
    total = int(frontend_conn.recv())

    progress(0, desc="Starting...")
    for i in progress.tqdm(range(0,total), desc="Downloading"):
        _ = int(frontend_conn.recv())
    return gr.update(interactive=False, visible=False)

def data_resize(resize_checkbox_group, progress=gr.Progress()):
    if not "skip_resize" in resize_checkbox_group:
        # thread block and wait for response
        total = int(frontend_conn.recv())

        progress(0, desc="Starting...")
        for i in progress.tqdm(range(total), desc="Resizing"):
            _ = frontend_conn.recv()

    frontend_conn.close()
    del e6_downloader, frontend_conn, backend_conn
    return gr.update(interactive=False, visible=False)

def end_connection():
    e6_downloader.join()



def merge_dict(path1, path2, path3):
    png_list = glob.glob(os.path.join(path1, f"*.png"))
    png_list = [x.replace(f".png", f".txt") for x in png_list]

    jpg_list = glob.glob(os.path.join(path2, f"*.jpg"))
    jpg_list = [x.replace(f".jpg", f".txt") for x in jpg_list]

    gif_list = glob.glob(os.path.join(path3, f"*.gif"))
    gif_list = [x.replace(f".gif", f".txt") for x in gif_list]

    temp = {}
    temp["png"] = parse_files_all_tags(png_list)
    temp["jpg"] = parse_files_all_tags(jpg_list)
    temp["gif"] = parse_files_all_tags(gif_list)
    temp["searched"] = {}

    return temp.copy()


def show_gallery(folder_type_select):
    global all_images_dict
    # clear searched dict
    if "searched" in all_images_dict:
        del all_images_dict["searched"]
        all_images_dict["searched"] = {}

    folder_path = os.path.join(cwd, settings_json["batch_folder"])
    folder_path = os.path.join(folder_path, settings_json["downloaded_posts_folder"])
    folder_path = os.path.join(folder_path, settings_json[f"{folder_type_select}_folder"])
    images = glob.glob(os.path.join(folder_path, f"*.{folder_type_select}"))

    global is_csv_loaded
    if not is_csv_loaded:
        full_path_downloads = os.path.join(os.path.join(cwd, settings_json["batch_folder"]),
                                           settings_json["downloaded_posts_folder"])

        tag_count_dir = os.path.join(os.path.join(cwd, settings_json["batch_folder"]), settings_json["tag_count_list_folder"])

        is_csv_loaded = True
        global artist_csv_dict, character_csv_dict, species_csv_dict, general_csv_dict, meta_csv_dict, rating_csv_dict, tags_csv_dict
        artist_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "artist.csv"))
        character_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "character.csv"))
        species_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "species.csv"))
        general_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "general.csv"))
        meta_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "meta.csv"))
        rating_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "rating.csv"))
        tags_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "tags.csv"))

        all_images_dict = merge_dict(os.path.join(full_path_downloads, settings_json[f"png_folder"]),
                                     os.path.join(full_path_downloads, settings_json[f"jpg_folder"]),
                                     os.path.join(full_path_downloads, settings_json[f"gif_folder"]))
        # verbose_print(f"all_images_dict:\t\t{all_images_dict}")
    return gr.update(value=images, visible=True)

def change_config(file_path):
    temp = '\\' if is_windows() else '/'
    global settings_json
    global config_name
    if temp in file_path:
        settings_json = load_session_config(file_path)
        config_name = file_path
    else:
        settings_json = load_session_config(os.path.join(cwd, file_path))
        config_name = os.path.join(cwd, file_path)

    batch_folder = gr.update(value=settings_json["batch_folder"])
    resized_img_folder = gr.update(value=settings_json["resized_img_folder"])
    tag_sep = gr.update(value=settings_json["tag_sep"])
    tag_order_format = gr.update(value=settings_json["tag_order_format"])
    prepend_tags = gr.update(value=settings_json["prepend_tags"])
    append_tags = gr.update(value=settings_json["append_tags"])
    img_ext = gr.update(value=settings_json["img_ext"])
    method_tag_files = gr.update(value=settings_json["method_tag_files"])
    min_score = gr.update(value=settings_json["min_score"])
    min_fav_count = gr.update(value=settings_json["min_fav_count"])
    min_month = gr.update(value=settings_json["min_month"])
    min_day = gr.update(value=settings_json["min_day"])
    min_year = gr.update(value=settings_json["min_year"])
    min_area = gr.update(value=settings_json["min_area"])
    top_n = gr.update(value=settings_json["top_n"])
    min_short_side = gr.update(value=settings_json["min_short_side"])
    collect_checkbox_group_var = gr.update(choices=collect_checkboxes, value=grab_pre_selected(settings_json, collect_checkboxes))
    download_checkbox_group_var = gr.update(choices=download_checkboxes, value=grab_pre_selected(settings_json, download_checkboxes))
    resize_checkbox_group_var = gr.update(choices=resize_checkboxes, value=grab_pre_selected(settings_json, resize_checkboxes))
    required_tags_group_var = gr.update(choices=settings_json["required_tags"], value=[])
    blacklist_group_var = gr.update(choices=settings_json["blacklist"], value=[])
    skip_posts_file = gr.update(value=settings_json["skip_posts_file"])
    skip_posts_type = gr.update(value=settings_json["skip_posts_type"])
    collect_from_listed_posts_file = gr.update(value=settings_json["collect_from_listed_posts_file"])
    collect_from_listed_posts_type = gr.update(value=settings_json["collect_from_listed_posts_type"])
    apply_filter_to_listed_posts = gr.update(value=settings_json["apply_filter_to_listed_posts"])
    save_searched_list_type = gr.update(value=settings_json["save_searched_list_type"])
    save_searched_list_path = gr.update(value=settings_json["save_searched_list_path"])
    downloaded_posts_folder = gr.update(value=settings_json["downloaded_posts_folder"])
    png_folder = gr.update(value=settings_json["png_folder"])
    jpg_folder = gr.update(value=settings_json["jpg_folder"])
    webm_folder = gr.update(value=settings_json["webm_folder"])
    gif_folder = gr.update(value=settings_json["gif_folder"])
    swf_folder = gr.update(value=settings_json["swf_folder"])
    save_filename_type = gr.update(value=settings_json["save_filename_type"])
    remove_tags_list = gr.update(value=settings_json["remove_tags_list"])
    replace_tags_list = gr.update(value=settings_json["replace_tags_list"])
    tag_count_list_folder = gr.update(value=settings_json["tag_count_list_folder"])

    verbose_print(f"{settings_json}")
    verbose_print(f"json key count: {len(settings_json)}")

    global is_csv_loaded
    is_csv_loaded = False

    return batch_folder,resized_img_folder,tag_sep,tag_order_format,prepend_tags,append_tags,img_ext,method_tag_files,min_score,min_fav_count,min_year,min_month, \
           min_day,min_area,top_n,min_short_side,collect_checkbox_group_var,download_checkbox_group_var,resize_checkbox_group_var,required_tags_group_var, \
           blacklist_group_var,skip_posts_file,skip_posts_type,collect_from_listed_posts_file,collect_from_listed_posts_type,apply_filter_to_listed_posts, \
           save_searched_list_type,save_searched_list_path,downloaded_posts_folder,png_folder,jpg_folder,webm_folder,gif_folder,swf_folder,save_filename_type, \
           remove_tags_list,replace_tags_list,tag_count_list_folder

def print_hello():
    verbose_print(f"HELLO WORLD!")

def get_img_tags(gallery_comp):
    gallery_comp = str(gallery_comp[0])
    verbose_print(f"gallery_comp:\t\t{gallery_comp}")
    temp = '\\' if is_windows() else '/'
    gallery_comp = gallery_comp.split(temp)[-1]  # name w/ extn
    download_folder_type = gallery_comp.split(".")[-1] # get ext type
    verbose_print(f"download_folder_type:\t\t{download_folder_type}")

    gallery_comp = gallery_comp.replace(f".{download_folder_type}", ".txt")
    img_name = gallery_comp.split(f".txt")[0]
    img_name = str(img_name)
    full_path_downloads = os.path.join(os.path.join(cwd, settings_json["batch_folder"]), settings_json["downloaded_posts_folder"])
    full_path_gallery_type = os.path.join(full_path_downloads, settings_json[f"{download_folder_type}_folder"])
    full_path = os.path.join(full_path_gallery_type, f"{img_name}.txt")

    ### POPULATE all categories for selected image
    if not all_images_dict:
        raise ValueError('radio button not pressed i.e. image type button')

    verbose_print(f"gallery_comp:\t\t{gallery_comp}")
    verbose_print(f"img_name:\t\t{img_name}")
    verbose_print(f"full_path:\t\t{full_path}")

    img_tag_list = all_images_dict[download_folder_type][img_name]

    verbose_print(f"img_tag_list:\t\t{img_tag_list}")

    temp_tag_dict = {}
    temp_list = [[],[],[],[],[],[]]
    for tag in img_tag_list:
        if tag in artist_csv_dict:
            temp_list[0].append(tag)
        if tag in character_csv_dict:
            temp_list[1].append(tag)
        if tag in species_csv_dict:
            temp_list[2].append(tag)
        if tag in general_csv_dict:
            temp_list[3].append(tag)
        if tag in meta_csv_dict:
            temp_list[4].append(tag)
        if tag in rating_csv_dict:
            temp_list[5].append(tag)
    temp_tag_dict["artist"] = temp_list[0]
    temp_tag_dict["character"] = temp_list[1]
    temp_tag_dict["species"] = temp_list[2]
    temp_tag_dict["general"] = temp_list[3]
    temp_tag_dict["meta"] = temp_list[4]
    temp_tag_dict["rating"] = temp_list[5]

    artist_comp_checkboxgroup = gr.update(choices=temp_tag_dict["artist"])
    character_comp_checkboxgroup = gr.update(choices=temp_tag_dict["character"])
    species_comp_checkboxgroup = gr.update(choices=temp_tag_dict["species"])
    general_comp_checkboxgroup = gr.update(choices=temp_tag_dict["general"])
    meta_comp_checkboxgroup = gr.update(choices=temp_tag_dict["meta"])
    rating_comp_checkboxgroup = gr.update(choices=temp_tag_dict["rating"])

    # verbose_print(f"======================")
    # verbose_print(f"temp_tag_dict:\t\t{temp_tag_dict}")
    # verbose_print(f"img_name:\t\t{img_name}")
    # verbose_print(f"download_folder_type:\t\t{download_folder_type}")
    # verbose_print(f"======================")

    global selected_image_dict # id -> {categories: tag/s}, type -> string
    selected_image_dict = {}
    selected_image_dict[img_name] = temp_tag_dict.copy()
    selected_image_dict["type"] = download_folder_type

    verbose_print(f"selected_image_dict:\t\t{selected_image_dict}")

    return gr.update(value=img_name), artist_comp_checkboxgroup, character_comp_checkboxgroup, species_comp_checkboxgroup, general_comp_checkboxgroup, meta_comp_checkboxgroup, rating_comp_checkboxgroup

def filter_images_by_tags(input_tags, allowed_image_types):
    global all_images_dict
    # clear searched dict
    del all_images_dict["searched"]
    all_images_dict["searched"] = {}
    # remove possible checked searched flag
    if "searched" in allowed_image_types:
        allowed_image_types.remove("searched")

    input_tags_list = input_tags.split(" ")#[tag.strip() for tag in input_tags.split(',')]
    positive_tags = [str(tag) for tag in input_tags_list if not tag.startswith('-')]
    negative_tags = [str(tag[1:]) for tag in input_tags_list if tag.startswith('-')]

    if allowed_image_types is None:
        allowed_image_types = all_images_dict.keys()

    filtered_images = {ext: {} for ext in allowed_image_types}

    for ext, images in all_images_dict.items():
        if ext in allowed_image_types:
            for image_id, tags in images.items():
                if all(tag in tags for tag in positive_tags) and not any(tag in tags for tag in negative_tags):
                    filtered_images[str(ext)][str(image_id)] = tags
    all_images_dict["searched"] = filtered_images.copy()
    verbose_print(f"===============================")
    verbose_print(f"all_images_dict[\"searched\"]:\t\t{all_images_dict['searched']}")
    verbose_print(f"===============================")

def update_search_gallery():
    global all_images_dict
    folder_path = os.path.join(cwd, settings_json["batch_folder"])
    folder_path = os.path.join(folder_path, settings_json["downloaded_posts_folder"])
    images = []
    for ext in list(all_images_dict["searched"].keys()):
        search_path = os.path.join(folder_path, settings_json[f"{ext}_folder"])
        for img_id in list(all_images_dict["searched"][ext].keys()):
            images.append(os.path.join(search_path, f"{img_id}.{ext}"))
    return images

def search_tags(tag_search_textbox, global_search_opts):
    # update SEARCHED in global dictionary
    filter_images_by_tags(tag_search_textbox, global_search_opts)
    # return updated gallery
    images = update_search_gallery()
    return gr.update(value=images, visible=True)

def write_tags_to_text_file(input_string, file_path):
    with open(file_path, 'w') as file:
        file.write(input_string)

def dict_to_sorted_list(d):
    return sorted([[k, v] for k, v in d.items()], key=lambda x: x[1], reverse=True)

def write_tags_to_csv(dictionary, file_path):
    temp = '\\' if is_windows() else '/'
    csv_name = (file_path.split(temp)[-1]).split('.csv')[0]
    header_string = f"{csv_name},count"
    if "tags" in header_string:
        header_string = f"tag,count"
    # sort tags descending by frequency
    sort_dictionary_to_list = dict_to_sorted_list(dictionary)

    with open(file_path, 'w') as file:
        file.write(f"{header_string}\n")
        for pair in sort_dictionary_to_list:
            file.write(f"{pair[0]},{pair[1]}")
    file.close()

def save_tag_changes():
    # do a full save of all tags
    full_path_downloads = os.path.join(os.path.join(cwd, settings_json["batch_folder"]), settings_json["downloaded_posts_folder"])

    if not all_images_dict or not "png" in all_images_dict:
        raise ValueError('radio button not pressed i.e. image type button')

    verbose_print(f"++++++++++++++++++++++++++")
    temp_list = list(all_images_dict.keys())
    verbose_print(f"temp_list:\t\t{temp_list}")
    # if NONE: save self (selected_image)
    # if temp_list


    if "searched" in temp_list:
        temp_list.remove("searched")
        verbose_print(f"removing searched key")
        verbose_print(f"temp_list:\t\t{temp_list}")
    for ext in temp_list:
        full_path_gallery_type = os.path.join(full_path_downloads, settings_json[f"{ext}_folder"])
        for img_id in list(all_images_dict[ext]):
            full_path = os.path.join(full_path_gallery_type, f"{img_id}.txt")
            temp_tag_string = ",".join(all_images_dict[ext][img_id])
            write_tags_to_text_file(temp_tag_string, full_path)

    tag_count_dir = os.path.join(os.path.join(cwd, settings_json["batch_folder"]),
                                 settings_json["tag_count_list_folder"])
    # update csv stats files
    global artist_csv_dict, character_csv_dict, species_csv_dict, general_csv_dict, meta_csv_dict, rating_csv_dict, tags_csv_dict
    write_tags_to_csv(artist_csv_dict, os.path.join(tag_count_dir, "artist.csv"))
    write_tags_to_csv(character_csv_dict, os.path.join(tag_count_dir, "character.csv"))
    write_tags_to_csv(species_csv_dict, os.path.join(tag_count_dir, "species.csv"))
    write_tags_to_csv(general_csv_dict, os.path.join(tag_count_dir, "general.csv"))
    write_tags_to_csv(meta_csv_dict, os.path.join(tag_count_dir, "meta.csv"))
    write_tags_to_csv(rating_csv_dict, os.path.join(tag_count_dir, "rating.csv"))
    write_tags_to_csv(tags_csv_dict, os.path.join(tag_count_dir, "tags.csv"))
    verbose_print(f"SAVE COMPLETE")

def add_to_csv_dictionaries(string_category, tag):
    global artist_csv_dict, character_csv_dict, species_csv_dict, general_csv_dict, meta_csv_dict, rating_csv_dict, tags_csv_dict
    if string_category in "artist":
        if tag in list(artist_csv_dict.keys()):
            artist_csv_dict[tag] = artist_csv_dict[tag] + 1
        else:
            artist_csv_dict[tag] = 1
    if string_category in "character":
        if tag in list(character_csv_dict.keys()):
            character_csv_dict[tag] = character_csv_dict[tag] + 1
        else:
            character_csv_dict[tag] = 1
    if string_category in "species":
        if tag in list(species_csv_dict.keys()):
            species_csv_dict[tag] = species_csv_dict[tag] + 1
        else:
            species_csv_dict[tag] = 1
    if string_category in "general":
        if tag in list(general_csv_dict.keys()):
            general_csv_dict[tag] = general_csv_dict[tag] + 1
        else:
            general_csv_dict[tag] = 1
    if string_category in "meta":
        if tag in list(meta_csv_dict.keys()):
            meta_csv_dict[tag] = meta_csv_dict[tag] + 1
        else:
            meta_csv_dict[tag] = 1
    if string_category in "rating":
        if tag in list(rating_csv_dict.keys()):
            rating_csv_dict[tag] = rating_csv_dict[tag] + 1
        else:
            rating_csv_dict[tag] = 1
    # change the global tag csv
    if tag in list(tags_csv_dict.keys()):
        tags_csv_dict[tag] = tags_csv_dict[tag] + 1
    else:
        tags_csv_dict[tag] = 1

# this method only effects ONE category at a time
# selected_img has the form:
#     id -> {categories: [tags]}
#     type -> ext
def add_tag_changes(tag_string, string_category, apply_to_all_type_select_checkboxgroup, img_id):
    tag_list = tag_string.replace(" ", "").split(",")
    img_id = str(img_id)

    global all_images_dict
    global selected_image_dict
    category_component = None

    # updates selected image ONLY when it ( IS ) specified AND its TYPE is specified for edits in "apply_to_all_type_select_checkboxgroup"
    if img_id and len(img_id) > 0 and selected_image_dict and selected_image_dict["type"] in apply_to_all_type_select_checkboxgroup:
        # update info for selected image
        for tag in tag_list:
            if not tag in selected_image_dict[img_id][string_category]:
                selected_image_dict[img_id][string_category].append(tag)
        # update info for category components
        verbose_print(f"selected_image_dict[img_id][string_category]:\t\t{selected_image_dict[img_id][string_category]}")
        category_component = gr.update(choices=selected_image_dict[img_id][string_category], value=[])
    elif img_id and len(img_id) > 0 and selected_image_dict and (not apply_to_all_type_select_checkboxgroup or len(apply_to_all_type_select_checkboxgroup) == 0):
        # update info for selected image
        for tag in tag_list:
            if not tag in selected_image_dict[img_id][string_category]:
                selected_image_dict[img_id][string_category].append(tag)
        # update info for category components
        verbose_print(f"selected_image_dict[img_id][string_category]:\t\t{selected_image_dict[img_id][string_category]}")
        category_component = gr.update(choices=selected_image_dict[img_id][string_category], value=[])

        # find image in searched : id
        if (selected_image_dict["type"] in list(all_images_dict['searched'].keys())) and (img_id in list(all_images_dict["searched"][selected_image_dict["type"]].keys())):
            for tag in tag_list:
                if not tag in all_images_dict["searched"][selected_image_dict["type"]][img_id]:
                    all_images_dict["searched"][selected_image_dict["type"]][img_id].append(tag)
                    all_images_dict[selected_image_dict["type"]][img_id].append(tag)
                    # create or increment category table AND frequency table for (all) tags
                    add_to_csv_dictionaries(string_category, tag)
        elif img_id in list(all_images_dict[selected_image_dict["type"]].keys()): # find image in ( TYPE ) : id
            for tag in tag_list:
                if not tag in all_images_dict[selected_image_dict["type"]][img_id]:
                    all_images_dict[selected_image_dict["type"]][img_id].append(tag)
                    # create or increment category table AND frequency table for (all) tags
                    add_to_csv_dictionaries(string_category, tag)

    if len(apply_to_all_type_select_checkboxgroup) > 0:
        if "searched" in apply_to_all_type_select_checkboxgroup: # edit searched and then all the instances of the respective types
            for key_type in list(all_images_dict["searched"].keys()):
                for img_id in list(all_images_dict["searched"][key_type].keys()):
                    for tag in tag_list:
                        if not tag in all_images_dict["searched"][key_type][img_id]: # add tag
                            all_images_dict["searched"][key_type][img_id].append(tag)
                            all_images_dict[key_type][img_id].append(tag)
                            # create or increment category table AND frequency table for (all) tags
                            add_to_csv_dictionaries(string_category, tag)
        else:
            for key_type in apply_to_all_type_select_checkboxgroup:
                for img_id in list(all_images_dict[key_type].keys()):
                    for tag in tag_list:
                        if not tag in all_images_dict[key_type][img_id]:
                            all_images_dict[key_type][img_id].append(tag)
                            if "searched" in all_images_dict and key_type in all_images_dict["searched"] and img_id in all_images_dict["searched"][key_type]:
                                all_images_dict["searched"][key_type][img_id].append(tag)
                            # create or increment category table AND frequency table for (all) tags
                            add_to_csv_dictionaries(string_category, tag)
    return category_component

def remove_to_csv_dictionaries(string_category, tag):
    global artist_csv_dict, character_csv_dict, species_csv_dict, general_csv_dict, meta_csv_dict, rating_csv_dict, tags_csv_dict
    if string_category in "artist":
        if tag in list(artist_csv_dict.keys()):
            artist_csv_dict[tag] = artist_csv_dict[tag] - 1
        if artist_csv_dict[tag] == 0:
            del artist_csv_dict[tag]
    if string_category in "character":
        if tag in list(character_csv_dict.keys()):
            character_csv_dict[tag] = character_csv_dict[tag] - 1
        if character_csv_dict[tag] == 0:
            del character_csv_dict[tag]
    if string_category in "species":
        if tag in list(species_csv_dict.keys()):
            species_csv_dict[tag] = species_csv_dict[tag] - 1
        if species_csv_dict[tag] == 0:
            del species_csv_dict[tag]
    if string_category in "general":
        if tag in list(general_csv_dict.keys()):
            general_csv_dict[tag] = general_csv_dict[tag] - 1
        if general_csv_dict[tag] == 0:
            del general_csv_dict[tag]
    if string_category in "meta":
        if tag in list(meta_csv_dict.keys()):
            meta_csv_dict[tag] = meta_csv_dict[tag] - 1
        if meta_csv_dict[tag] == 0:
            del meta_csv_dict[tag]
    if string_category in "rating":
        if tag in list(rating_csv_dict.keys()):
            rating_csv_dict[tag] = rating_csv_dict[tag] - 1
        if rating_csv_dict[tag] == 0:
            del rating_csv_dict[tag]
    # change the global tag csv
    if tag in list(tags_csv_dict.keys()):
        tags_csv_dict[tag] = tags_csv_dict[tag] - 1
    if tags_csv_dict[tag] == 0:
        del tags_csv_dict[tag]

def remove_tag_changes(category_tag_checkbox_group, string_category, apply_to_all_type_select_checkboxgroup, img_id):
    tag_list = category_tag_checkbox_group
    img_id = str(img_id)

    global all_images_dict
    global selected_image_dict
    category_component = None

    # updates selected image ONLY when it ( IS ) specified AND its TYPE is specified for edits in "apply_to_all_type_select_checkboxgroup"
    if img_id and len(img_id) > 0 and selected_image_dict and selected_image_dict[
        "type"] in apply_to_all_type_select_checkboxgroup:
        # update info for selected image
        for tag in tag_list:
            if tag in selected_image_dict[img_id][string_category]:
                selected_image_dict[img_id][string_category].remove(tag)
        # update info for category components
        verbose_print(
            f"selected_image_dict[img_id][string_category]:\t\t{selected_image_dict[img_id][string_category]}")
        category_component = gr.update(choices=selected_image_dict[img_id][string_category], value=[])
    elif img_id and len(img_id) > 0 and selected_image_dict and (
            not apply_to_all_type_select_checkboxgroup or len(apply_to_all_type_select_checkboxgroup) == 0):
        # update info for selected image
        for tag in tag_list:
            if tag in selected_image_dict[img_id][string_category]:
                selected_image_dict[img_id][string_category].remove(tag)
        # update info for category components
        verbose_print(
            f"selected_image_dict[img_id][string_category]:\t\t{selected_image_dict[img_id][string_category]}")
        category_component = gr.update(choices=selected_image_dict[img_id][string_category], value=[])

        # find image in searched : id
        if (selected_image_dict["type"] in list(all_images_dict['searched'].keys())) and (
                img_id in list(all_images_dict["searched"][selected_image_dict["type"]].keys())):
            for tag in tag_list:
                if tag in all_images_dict["searched"][selected_image_dict["type"]][img_id]:
                    all_images_dict["searched"][selected_image_dict["type"]][img_id].remove(tag)
                    all_images_dict[selected_image_dict["type"]][img_id].remove(tag)
                    # create or increment category table AND frequency table for (all) tags
                    remove_to_csv_dictionaries(string_category, tag)
        elif img_id in list(all_images_dict[selected_image_dict["type"]].keys()):  # find image in ( TYPE ) : id
            for tag in tag_list:
                if tag in all_images_dict[selected_image_dict["type"]][img_id]:
                    all_images_dict[selected_image_dict["type"]][img_id].remove(tag)
                    # create or increment category table AND frequency table for (all) tags
                    remove_to_csv_dictionaries(string_category, tag)

    if len(apply_to_all_type_select_checkboxgroup) > 0:
        if "searched" in apply_to_all_type_select_checkboxgroup:  # edit searched and then all the instances of the respective types
            for key_type in list(all_images_dict["searched"].keys()):
                for img_id in list(all_images_dict["searched"][key_type].keys()):
                    for tag in tag_list:
                        if tag in all_images_dict["searched"][key_type][img_id]:  # remove tag
                            all_images_dict["searched"][key_type][img_id].remove(tag)
                            all_images_dict[key_type][img_id].remove(tag)
                            # create or increment category table AND frequency table for (all) tags
                            remove_to_csv_dictionaries(string_category, tag)
        else:
            for key_type in apply_to_all_type_select_checkboxgroup:
                for img_id in list(all_images_dict[key_type].keys()):
                    for tag in tag_list:
                        if tag in all_images_dict[key_type][img_id]:
                            all_images_dict[key_type][img_id].remove(tag)
                            if "searched" in all_images_dict and key_type in all_images_dict[
                                "searched"] and img_id in all_images_dict["searched"][key_type]:
                                all_images_dict["searched"][key_type][img_id].remove(tag)
                            # create or increment category table AND frequency table for (all) tags
                            remove_to_csv_dictionaries(string_category, tag)
    return category_component

def is_csv_dict_empty(stats_load_file):
    tag_count_dir = os.path.join(os.path.join(cwd, settings_json["batch_folder"]),
                                 settings_json["tag_count_list_folder"])
    global artist_csv_dict, character_csv_dict, species_csv_dict, general_csv_dict, meta_csv_dict, rating_csv_dict, tags_csv_dict
    if "artist" in stats_load_file:
        value = len(list(artist_csv_dict.keys()))
        if (value == 0):
            artist_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "artist.csv"))
        return [artist_csv_dict.copy(), value]
    elif "character" in stats_load_file:
        value = len(list(character_csv_dict.keys()))
        if (value == 0):
            character_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "character.csv"))
        return [character_csv_dict.copy(), value]
    elif "species" in stats_load_file:
        value = len(list(species_csv_dict.keys()))
        if (value == 0):
            species_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "species.csv"))
        return [species_csv_dict.copy(), value]
    elif "general" in stats_load_file:
        value = len(list(general_csv_dict.keys()))
        if (value == 0):
            general_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "general.csv"))
        return [general_csv_dict.copy(), value]
    elif "meta" in stats_load_file:
        value = len(list(meta_csv_dict.keys()))
        if (value == 0):
            meta_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "meta.csv"))
        return [meta_csv_dict.copy(), value]
    elif "rating" in stats_load_file:
        value = len(list(rating_csv_dict.keys()))
        if (value == 0):
            rating_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "rating.csv"))
        return [rating_csv_dict.copy(), value]
    elif "tags" in stats_load_file:
        value = len(list(tags_csv_dict.keys()))
        if (value == 0):
            tags_csv_dict = parse_csv_all_tags(csv_file_path=os.path.join(tag_count_dir, "tags.csv"))
        return [tags_csv_dict.copy(), value]

def run_stats(stats_run_options, stats_load_file):
    csv_table, size = is_csv_dict_empty(stats_load_file)

    verbose_print(f"stats_run_options:\t\t{stats_run_options}")
    verbose_print(f"stats_load_file:\t\t{stats_load_file}")

    dataframe = None
    show_list = None
    if "frequency table" in stats_run_options:
        show_list = sorted(csv_table.items(), key=lambda x: x[1], reverse=True)
        dataframe = gr.update(visible=True, label=stats_run_options, max_rows=size,
                              value=show_list)
    elif "inverse freq table" in stats_run_options:
        total_sum = sum(csv_table.values())
        normalized_dict = {key: value / total_sum for key, value in csv_table.items()}
        show_list = sorted(normalized_dict.items(), key=lambda x: x[1], reverse=True)
        dataframe = gr.update(visible=True, label=stats_run_options, max_rows=size,
                              value=show_list)
    # verbose_print(f"show_list:\t\t{show_list}")
    return dataframe

'''
##################################################################################################################################
#######################################################     GUI BLOCKS     #######################################################
##################################################################################################################################
'''

### The below CSS is dependent on the version of Gradio the user has, (gradio DEVs should have this fixed in the next version 22.0 of gradio)
cyan_button_css = "label.svelte-1qxcj04.svelte-1qxcj04.svelte-1qxcj04 {background: linear-gradient(#00ffff, #2563eb)}"
red_button_css = "label.svelte-1qxcj04.svelte-1qxcj04.svelte-1qxcj04.selected {background: linear-gradient(#ff0000, #404040)}"
green_button_css = "label.svelte-1qxcj04.svelte-1qxcj04.svelte-1qxcj04 {background: linear-gradient(#2fa614, #2563eb)}"

with gr.Blocks(css=f"{green_button_css} {red_button_css}") as demo:
    with gr.Tab("General Config"):
        with gr.Row():
            config_save_var0 = gr.Button(value="Apply & Save Settings", variant='primary')
        gr.Markdown(
        """
        ### Make sure all necessary dependencies have been installed.
        ### Questions about certain features can be found here: https://github.com/pikaflufftuft/pikaft-e621-posts-downloader
        ### This UI currently works in the case of ( SINGLE ) batch configurations
        """)
        with gr.Row():
            with gr.Column():
                batch_folder = gr.Textbox(lines=1, label='Path to Batch Directory', value=settings_json["batch_folder"])
            with gr.Column():
                resized_img_folder = gr.Textbox(lines=1, label='Path to Resized Images', value=settings_json["resized_img_folder"])
        with gr.Row():
            tag_sep = gr.Textbox(lines=1, label='Tag Seperator/Delimeter', value=settings_json["tag_sep"])
            tag_order_format = gr.Textbox(lines=1, label='Tag ORDER', value=settings_json["tag_order_format"])
            prepend_tags = gr.Textbox(lines=1, label='Prepend Tags', value=settings_json["prepend_tags"])
            append_tags = gr.Textbox(lines=1, label='Append Tags', value=settings_json["append_tags"])
        with gr.Row():
            with gr.Column():
                img_ext = gr.Dropdown(choices=img_extensions, label='Image Extension', value=settings_json["img_ext"])
            with gr.Column():
                method_tag_files = gr.Radio(choices=method_tag_files_opts, label='Resized Img Tag Handler', value=settings_json["method_tag_files"])
            with gr.Column():
                settings_path = gr.Textbox(lines=1, label='Path to JSON (REQUIRED)', value=config_name)
            with gr.Column():
                create_new_config_checkbox = gr.Checkbox(label="Create NEW Config", value=False)
                load_json_file_button = gr.Button(value="Load from JSON", variant='secondary')

    with gr.Tab("Stats Config"):
        with gr.Row():
            config_save_var1 = gr.Button(value="Apply & Save Settings", variant='primary')
        with gr.Row():
            min_score = gr.Slider(minimum=0, maximum=10000, step=1, label='Filter: Min Score', value=settings_json["min_score"])
        with gr.Row():
            min_fav_count = gr.Slider(minimum=0, maximum=10000, step=1, label='Filter: Min Fav Count', value=settings_json["min_fav_count"])
        with gr.Row():
            with gr.Column():
                min_year = gr.Slider(minimum=2000, maximum=2050, step=1, label='Filter: Min Year', value=int(settings_json["min_year"]))
                min_month = gr.Slider(minimum=1, maximum=12, step=1, label='Filter: Min Month',
                                     value=int(settings_json["min_month"]))
                min_day = gr.Slider(minimum=1, maximum=31, step=1, label='Filter: Min Day',
                                     value=int(settings_json["min_day"]))
        with gr.Row():
            min_area = gr.Slider(minimum=1, maximum=1000000, step=1, label='Filter: Min Area', value=settings_json["min_area"])
        with gr.Row():
            top_n = gr.Slider(minimum=0, maximum=10000, step=1, label='Filter: Top N', value=settings_json["top_n"])
        with gr.Row():
            min_short_side = gr.Slider(minimum=1, maximum=100000, step=1, label='Resize Param: Min Short Side', value=settings_json["min_short_side"])

    with gr.Tab("Checkbox Config"):
        with gr.Row():
            config_save_var2 = gr.Button(value="Apply & Save Settings", variant='primary')
        with gr.Row():
            with gr.Column():
                gr.Markdown(
                """
                ### Data Collection Options
                """)
                collect_checkbox_group_var = gr.CheckboxGroup(choices=collect_checkboxes, label='Collect Checkboxes', value=grab_pre_selected(settings_json, collect_checkboxes))
            with gr.Column():
                gr.Markdown(
                """
                ###  Data Download Options
                """)
                download_checkbox_group_var = gr.CheckboxGroup(choices=download_checkboxes, label='Download Checkboxes', value=grab_pre_selected(settings_json, download_checkboxes))
            with gr.Column():
                gr.Markdown(
                """
                ###  Data Resize Options
                """)
                resize_checkbox_group_var = gr.CheckboxGroup(choices=resize_checkboxes, label='Resize Checkboxes', value=grab_pre_selected(settings_json, resize_checkboxes))

    with gr.Tab("Required Tags Config"):
        with gr.Row():
            config_save_var3 = gr.Button(value="Apply & Save Settings", variant='primary')
        with gr.Row():
            with gr.Column():
                required_tags = gr.Textbox(lines=1, label='Press Enter to ADD tag/s (E.g. tag1    or    tag1, tag2, ..., etc.)', value="")
                remove_button_required = gr.Button(value="Remove Checked Tags", variant='secondary')
            with gr.Column():
                file_all_tags_list_required = gr.File(file_count="multiple", file_types=["file"], label="Select ALL files with Tags to be parsed and Added")
                parse_button_required = gr.Button(value="Parse/Add Tags", variant='secondary')
        with gr.Row():
            required_tags_group_var = gr.CheckboxGroup(choices=required_tags_list, label='ALL Required Tags', value=[])

    with gr.Tab("Blacklist Tags Config"):
        with gr.Row():
            config_save_var4 = gr.Button(value="Apply & Save Settings", variant='primary')
        with gr.Row():
            with gr.Column():
                blacklist = gr.Textbox(lines=1, label='Press Enter to ADD tag/s (E.g. tag1    or    tag1, tag2, ..., etc.)', value="")
                remove_button_blacklist = gr.Button(value="Remove Checked Tags", variant='secondary')
            with gr.Column():
                file_all_tags_list_blacklist = gr.File(file_count="multiple", file_types=["file"], label="Select ALL files with Tags to be parsed and Added")
                parse_button_blacklist = gr.Button(value="Parse/Add Tags", variant='secondary')
        with gr.Row():
            blacklist_group_var = gr.CheckboxGroup(choices=blacklist_tags, label='ALL Blacklisted Tags', value=[])

    with gr.Tab("Additional Components Config"):
        with gr.Row():
            config_save_var5 = gr.Button(value="Apply & Save Settings", variant='primary')
        with gr.Row():
            with gr.Column():
                skip_posts_file = gr.Textbox(lines=1, label='Path to file w/ multiple id/md5 to skip',
                                             value=settings_json["skip_posts_file"])
                skip_posts_type = gr.Radio(choices=["id","md5"], label='id/md5 skip', value=settings_json["skip_posts_type"])
            with gr.Column():
                save_searched_list_path = gr.Textbox(lines=1, label='id/md5 list to file path', value=settings_json["save_searched_list_path"])
                save_searched_list_type = gr.Radio(choices=["id", "md5", "None"], label='Save id/md5 list to file', value=settings_json["save_searched_list_type"])
        with gr.Row():
            with gr.Column():
                apply_filter_to_listed_posts = gr.Checkbox(label='Apply Filters to Collected Posts',
                                                   value=settings_json["apply_filter_to_listed_posts"])
                collect_from_listed_posts_type = gr.Radio(choices=["id", "md5"], label='id/md5 collect',
                                                          value=settings_json["collect_from_listed_posts_type"])
                collect_from_listed_posts_file = gr.Textbox(lines=1, label='Path to file w/ multiple id/md5 to collect',
                                                            value=settings_json["collect_from_listed_posts_file"])
        with gr.Row():
            downloaded_posts_folder = gr.Textbox(lines=1, label='Path for downloaded posts',
                                                 value=settings_json["downloaded_posts_folder"])
            png_folder = gr.Textbox(lines=1, label='Path for png data', value=settings_json["png_folder"])
            jpg_folder = gr.Textbox(lines=1, label='Path for jpg data', value=settings_json["jpg_folder"])
            webm_folder = gr.Textbox(lines=1, label='Path for webm data', value=settings_json["webm_folder"])
            gif_folder = gr.Textbox(lines=1, label='Path for gif data', value=settings_json["gif_folder"])
            swf_folder = gr.Textbox(lines=1, label='Path for swf data', value=settings_json["swf_folder"])
        with gr.Row():
            save_filename_type = gr.Radio(choices=["id","md5"], label='Select Filename Type', value=settings_json["save_filename_type"])
            remove_tags_list = gr.Textbox(lines=1, label='Path to negative tags file', value=settings_json["remove_tags_list"])
            replace_tags_list = gr.Textbox(lines=1, label='Path to replace tags file', value=settings_json["replace_tags_list"])
            tag_count_list_folder = gr.Textbox(lines=1, label='Path to tag count file', value=settings_json["tag_count_list_folder"])

    with gr.Tab("Run Tab"):
        with gr.Row():
            with gr.Column():
                basefolder = gr.Textbox(lines=1, label='Root Output Dir Path', value=cwd)
                numcpu = gr.Slider(minimum=1, maximum=mp.cpu_count(), step=1, label='Worker Threads', value=int(mp.cpu_count()/2))
        with gr.Row():
            with gr.Column():
               phaseperbatch = gr.Checkbox(label='Completes all phases per batch', value=True)
            with gr.Column():
               keepdb = gr.Checkbox(label='Keep e6 db data', value=False)
            with gr.Column():
                cachepostsdb = gr.Checkbox(label='cache e6 posts file when multiple batches', value=False)
        with gr.Row():
            postscsv = gr.Textbox(lines=1, label='Path to e6 posts csv', value="")
            tagscsv = gr.Textbox(lines=1, label='Path to e6 tags csv', value="")
            postsparquet = gr.Textbox(lines=1, label='Path to e6 posts parquet', value="")
            tagsparquet = gr.Textbox(lines=1, label='Path to e6 tags parquet', value="")
            aria2cpath = gr.Textbox(lines=1, label='Path to aria2c program', value="")
        with gr.Row():
            run_button = gr.Button(value="Run", variant='primary')
        with gr.Row():
            progress_bar_textbox_collect = gr.Textbox(interactive=False, visible=False)
        with gr.Row():
            progress_bar_textbox_download = gr.Textbox(interactive=False, visible=False)
        with gr.Row():
            progress_bar_textbox_resize = gr.Textbox(interactive=False, visible=False)
        with gr.Accordion("Batch Run"):
            with gr.Row():
                temp = '\\' if is_windows() else '/'
                all_json_files_checkboxgroup = gr.CheckboxGroup(choices=[(each_settings_file.split(temp)[-1]) for each_settings_file in glob.glob(os.path.join(cwd, f"*.json"))],
                                                                label='Select to Run', value=[])
            with gr.Row():
                run_button_batch = gr.Button(value="Batch Run", variant='primary')
            with gr.Row():
                progress_run_batch = gr.Textbox(interactive=False, visible=False)
    with gr.Tab("Image Preview Gallery"):
        with gr.Row():
            with gr.Column():
                with gr.Row():
                    download_folder_type = gr.Radio(choices=file_extn_list, label='Select Filename Type')# webm, swf not yet supported
                    img_id_textbox = gr.Textbox(label="Image ID", interactive=False, lines=1, value="")
                with gr.Row():
                    tag_search_textbox = gr.Textbox(label="Search e621 tags the same way as the site prepend the minus symbol to make the tag negative E.G. anthro -fox", lines=1, value="")
                with gr.Row():
                    apply_to_all_type_select_checkboxgroup = gr.CheckboxGroup(choices=["png", "jpg", "gif", "searched"], label=f'Apply\'s to ALL of {["png", "jpg", "gif", "searched"]} type', value=[])
                with gr.Row():
                    tag_remove_button = gr.Button(value="Remove Selected", variant='primary')
                    tag_save_button = gr.Button(value="Save Changes", variant='primary')

                with gr.Row():
                    tag_add_artist_textbox = gr.Textbox(label="Artist: Press Enter to ADD tag/s (E.g. tag1 or tag1, tag2, ..., etc.)", lines=1, value="")
                img_artist_tag_checkbox_group = gr.CheckboxGroup(choices=[], label='Artist Tag/s', value=[])
                with gr.Row():
                    tag_add_character_textbox = gr.Textbox(label="Character: Press Enter to ADD tag/s (E.g. tag1 or tag1, tag2, ..., etc.)", lines=1, value="")
                img_character_tag_checkbox_group = gr.CheckboxGroup(choices=[], label='Character Tag/s', value=[])
                with gr.Row():
                    tag_add_species_textbox = gr.Textbox(label="Species: Press Enter to ADD tag/s (E.g. tag1 or tag1, tag2, ..., etc.)", lines=1, value="")
                img_species_tag_checkbox_group = gr.CheckboxGroup(choices=[], label='Species Tag/s', value=[])
                with gr.Row():
                    tag_add_general_textbox = gr.Textbox(label="General: Press Enter to ADD tag/s (E.g. tag1 or tag1, tag2, ..., etc.)", lines=1, value="")
                img_general_tag_checkbox_group = gr.CheckboxGroup(choices=[], label='General Tag/s', value=[])
                with gr.Row():
                    tag_add_meta_textbox = gr.Textbox(label="Meta: Press Enter to ADD tag/s (E.g. tag1 or tag1, tag2, ..., etc.)", lines=1, value="")
                img_meta_tag_checkbox_group = gr.CheckboxGroup(choices=[], label='Meta Tag/s', value=[])
                with gr.Row():
                    tag_add_rating_textbox = gr.Textbox(label="Rating: Press Enter to ADD tag/s (E.g. tag1 or tag1, tag2, ..., etc.)", lines=1, value="")
                img_rating_tag_checkbox_group = gr.CheckboxGroup(choices=[], label='Rating Tag/s', value=[])


            gallery_comp = gr.Gallery(visible=False, elem_id="gallery").style(grid=[3], height="auto")
    with gr.Tab("Data Stats"):
        with gr.Row():
            stats_run_options = gr.Dropdown(label="Run Method", choices=["frequency table", "inverse freq table"])
            stats_load_file = gr.Dropdown(label="Meta Tag Category", choices=["tags", "artist", "character", "species", "general", "meta", "rating"])
            stats_run_button = gr.Button(value="Run Stats", variant='primary')
        with gr.Row():
            stats_selected_data = gr.Dataframe(interactive=False, label="Dataframe Table", visible=False,
                                               headers=["Tag Category", "Count"], datatype=["str", "number"], max_cols=2,
                                               type="array")
        with gr.Row():
            tb_1 = gr.Textbox(visible=False, interactive=False, value="artist")
            tb_2 = gr.Textbox(visible=False, interactive=False, value="character")
            tb_3 = gr.Textbox(visible=False, interactive=False, value="species")
            tb_4 = gr.Textbox(visible=False, interactive=False, value="general")
            tb_5 = gr.Textbox(visible=False, interactive=False, value="meta")
            tb_6 = gr.Textbox(visible=False, interactive=False, value="rating")

    '''
    ##################################################################################################################################
    ####################################################     EVENT HANDLER/S     #####################################################
    ##################################################################################################################################
    '''

    stats_run_button.click(fn=run_stats, inputs=[stats_run_options, stats_load_file], outputs=[stats_selected_data])

    tag_remove_button.click(fn=remove_tag_changes, inputs=[img_artist_tag_checkbox_group, tb_1, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                outputs=[img_artist_tag_checkbox_group]).then(fn=remove_tag_changes, inputs=[img_character_tag_checkbox_group, tb_2, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                outputs=[img_character_tag_checkbox_group]).then(fn=remove_tag_changes, inputs=[img_species_tag_checkbox_group, tb_3, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                outputs=[img_species_tag_checkbox_group]).then(fn=remove_tag_changes, inputs=[img_general_tag_checkbox_group, tb_4, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                outputs=[img_general_tag_checkbox_group]).then(fn=remove_tag_changes, inputs=[img_meta_tag_checkbox_group, tb_5, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                outputs=[img_meta_tag_checkbox_group]).then(fn=remove_tag_changes, inputs=[img_rating_tag_checkbox_group, tb_6, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                outputs=[img_rating_tag_checkbox_group])

    tag_add_artist_textbox.submit(fn=add_tag_changes, inputs=[tag_add_artist_textbox, tb_1, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                                  outputs=[img_artist_tag_checkbox_group])
    tag_add_character_textbox.submit(fn=add_tag_changes, inputs=[tag_add_character_textbox, tb_2, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                                     outputs=[img_character_tag_checkbox_group])
    tag_add_species_textbox.submit(fn=add_tag_changes, inputs=[tag_add_species_textbox, tb_3, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                                   outputs=[img_species_tag_checkbox_group])
    tag_add_general_textbox.submit(fn=add_tag_changes, inputs=[tag_add_general_textbox, tb_4, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                                   outputs=[img_general_tag_checkbox_group])
    tag_add_meta_textbox.submit(fn=add_tag_changes, inputs=[tag_add_meta_textbox, tb_5, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                                outputs=[img_meta_tag_checkbox_group])
    tag_add_rating_textbox.submit(fn=add_tag_changes, inputs=[tag_add_rating_textbox, tb_6, apply_to_all_type_select_checkboxgroup, img_id_textbox],
                                  outputs=[img_rating_tag_checkbox_group])

    tag_save_button.click(fn=save_tag_changes,inputs=[], outputs=[])

    tag_search_textbox.submit(fn=search_tags, inputs=[tag_search_textbox, apply_to_all_type_select_checkboxgroup], outputs=[gallery_comp]).then(fn=reset_selected_img, inputs=[img_id_textbox],
                        outputs=[img_id_textbox, img_artist_tag_checkbox_group, img_character_tag_checkbox_group, img_species_tag_checkbox_group, img_general_tag_checkbox_group,
                                img_meta_tag_checkbox_group, img_rating_tag_checkbox_group])

    download_folder_type.change(fn=show_gallery, inputs=[download_folder_type], outputs=[gallery_comp]).then(fn=reset_selected_img, inputs=[img_id_textbox],
                        outputs=[img_id_textbox, img_artist_tag_checkbox_group, img_character_tag_checkbox_group, img_species_tag_checkbox_group, img_general_tag_checkbox_group,
                                img_meta_tag_checkbox_group, img_rating_tag_checkbox_group])

    gallery_comp.select(fn=print_hello,inputs=[],outputs=[]).then(fn=get_img_tags, inputs=[gallery_comp],
                        outputs=[img_id_textbox, img_artist_tag_checkbox_group, img_character_tag_checkbox_group,
                                 img_species_tag_checkbox_group, img_general_tag_checkbox_group,
                                 img_meta_tag_checkbox_group, img_rating_tag_checkbox_group],
                        _js="(g, d) => [document.querySelector(\'.selected img\').getAttribute(\'src\'), d]")

    load_json_file_button.click(fn=change_config, inputs=[settings_path], outputs=[batch_folder,resized_img_folder,
                tag_sep,tag_order_format,prepend_tags,append_tags,img_ext,method_tag_files,min_score,min_fav_count,
                min_year,min_month,min_day,min_area,top_n,min_short_side,collect_checkbox_group_var,
                download_checkbox_group_var,resize_checkbox_group_var,required_tags_group_var,blacklist_group_var,skip_posts_file,
                skip_posts_type,collect_from_listed_posts_file,collect_from_listed_posts_type,
                apply_filter_to_listed_posts,save_searched_list_type,save_searched_list_path,downloaded_posts_folder,
                png_folder,jpg_folder,webm_folder,gif_folder,swf_folder,save_filename_type,remove_tags_list,
                replace_tags_list,tag_count_list_folder])

    config_save_var0.click(fn=config_save_button,
                          inputs=[batch_folder,resized_img_folder,tag_sep,tag_order_format,prepend_tags,append_tags,
                                  img_ext,method_tag_files,min_score,min_fav_count,min_area,top_n,
                                  min_short_side,skip_posts_file,
                                  skip_posts_type,collect_from_listed_posts_file,collect_from_listed_posts_type,
                                  apply_filter_to_listed_posts,save_searched_list_type,save_searched_list_path,
                                  downloaded_posts_folder,png_folder,jpg_folder,webm_folder,gif_folder,swf_folder,
                                  save_filename_type,remove_tags_list,replace_tags_list,tag_count_list_folder,min_month,
                                  min_day,min_year,collect_checkbox_group_var,download_checkbox_group_var,resize_checkbox_group_var,create_new_config_checkbox,settings_path
                                  ],
                          outputs=[all_json_files_checkboxgroup]
                          )
    config_save_var1.click(fn=config_save_button,
                          inputs=[batch_folder,resized_img_folder,tag_sep,tag_order_format,prepend_tags,append_tags,
                                  img_ext,method_tag_files,min_score,min_fav_count,min_area,top_n,
                                  min_short_side,skip_posts_file,
                                  skip_posts_type,collect_from_listed_posts_file,collect_from_listed_posts_type,
                                  apply_filter_to_listed_posts,save_searched_list_type,save_searched_list_path,
                                  downloaded_posts_folder,png_folder,jpg_folder,webm_folder,gif_folder,swf_folder,
                                  save_filename_type,remove_tags_list,replace_tags_list,tag_count_list_folder,min_month,
                                  min_day,min_year,collect_checkbox_group_var,download_checkbox_group_var,resize_checkbox_group_var,create_new_config_checkbox,settings_path
                                  ],
                          outputs=[]
                          )
    config_save_var2.click(fn=config_save_button,
                          inputs=[batch_folder,resized_img_folder,tag_sep,tag_order_format,prepend_tags,append_tags,
                                  img_ext,method_tag_files,min_score,min_fav_count,min_area,top_n,
                                  min_short_side,skip_posts_file,
                                  skip_posts_type,collect_from_listed_posts_file,collect_from_listed_posts_type,
                                  apply_filter_to_listed_posts,save_searched_list_type,save_searched_list_path,
                                  downloaded_posts_folder,png_folder,jpg_folder,webm_folder,gif_folder,swf_folder,
                                  save_filename_type,remove_tags_list,replace_tags_list,tag_count_list_folder,min_month,
                                  min_day,min_year,collect_checkbox_group_var,download_checkbox_group_var,resize_checkbox_group_var,create_new_config_checkbox,settings_path
                                  ],
                          outputs=[]
                          )
    config_save_var3.click(fn=config_save_button,
                          inputs=[batch_folder,resized_img_folder,tag_sep,tag_order_format,prepend_tags,append_tags,
                                  img_ext,method_tag_files,min_score,min_fav_count,min_area,top_n,
                                  min_short_side,skip_posts_file,
                                  skip_posts_type,collect_from_listed_posts_file,collect_from_listed_posts_type,
                                  apply_filter_to_listed_posts,save_searched_list_type,save_searched_list_path,
                                  downloaded_posts_folder,png_folder,jpg_folder,webm_folder,gif_folder,swf_folder,
                                  save_filename_type,remove_tags_list,replace_tags_list,tag_count_list_folder,min_month,
                                  min_day,min_year,collect_checkbox_group_var,download_checkbox_group_var,resize_checkbox_group_var,create_new_config_checkbox,settings_path
                                  ],
                          outputs=[]
                          )
    config_save_var4.click(fn=config_save_button,
                          inputs=[batch_folder,resized_img_folder,tag_sep,tag_order_format,prepend_tags,append_tags,
                                  img_ext,method_tag_files,min_score,min_fav_count,min_area,top_n,
                                  min_short_side,skip_posts_file,
                                  skip_posts_type,collect_from_listed_posts_file,collect_from_listed_posts_type,
                                  apply_filter_to_listed_posts,save_searched_list_type,save_searched_list_path,
                                  downloaded_posts_folder,png_folder,jpg_folder,webm_folder,gif_folder,swf_folder,
                                  save_filename_type,remove_tags_list,replace_tags_list,tag_count_list_folder,min_month,
                                  min_day,min_year,collect_checkbox_group_var,download_checkbox_group_var,resize_checkbox_group_var,create_new_config_checkbox,settings_path
                                  ],
                          outputs=[]
                          )
    config_save_var5.click(fn=config_save_button,
                          inputs=[batch_folder,resized_img_folder,tag_sep,tag_order_format,prepend_tags,append_tags,
                                  img_ext,method_tag_files,min_score,min_fav_count,min_area,top_n,
                                  min_short_side,skip_posts_file,
                                  skip_posts_type,collect_from_listed_posts_file,collect_from_listed_posts_type,
                                  apply_filter_to_listed_posts,save_searched_list_type,save_searched_list_path,
                                  downloaded_posts_folder,png_folder,jpg_folder,webm_folder,gif_folder,swf_folder,
                                  save_filename_type,remove_tags_list,replace_tags_list,tag_count_list_folder,min_month,
                                  min_day,min_year,collect_checkbox_group_var,download_checkbox_group_var,resize_checkbox_group_var,create_new_config_checkbox,settings_path
                                  ],
                          outputs=[]
                          )

    run_button.click(fn=run_script,inputs=[basefolder,settings_path,numcpu,phaseperbatch,keepdb,cachepostsdb,postscsv,tagscsv,postsparquet,tagsparquet,aria2cpath],
                     outputs=[]).then(fn=make_run_visible,inputs=[],outputs=[progress_bar_textbox_collect]).then(fn=data_collect, inputs=[],
                     outputs=[progress_bar_textbox_collect]).then(fn=make_run_visible,inputs=[],outputs=[progress_bar_textbox_download]).then(fn=data_download, inputs=[],
                     outputs=[progress_bar_textbox_download]).then(fn=make_run_visible,inputs=[],outputs=[progress_bar_textbox_resize]).then(fn=data_resize, inputs=[resize_checkbox_group_var],
                     outputs=[progress_bar_textbox_resize]).then(fn=end_connection,inputs=[],outputs=[])

    run_button_batch.click(fn=make_run_visible,inputs=[],outputs=[progress_run_batch]).then(fn=run_script_batch,inputs=[basefolder,settings_path,numcpu,phaseperbatch,keepdb,cachepostsdb,postscsv,tagscsv,postsparquet,tagsparquet,aria2cpath,all_json_files_checkboxgroup],
                     outputs=[progress_run_batch])

    required_tags.submit(fn=textbox_handler_required, inputs=[required_tags], outputs=[required_tags,required_tags_group_var])
    blacklist.submit(fn=textbox_handler_blacklist, inputs=[blacklist], outputs=[blacklist,blacklist_group_var])

    remove_button_required.click(fn=check_box_group_handler_required, inputs=[required_tags_group_var], outputs=[required_tags_group_var])
    remove_button_blacklist.click(fn=check_box_group_handler_blacklist, inputs=[blacklist_group_var], outputs=[blacklist_group_var])

    parse_button_required.click(fn=parse_file_required, inputs=[file_all_tags_list_required], outputs=[required_tags_group_var])
    parse_button_blacklist.click(fn=parse_file_blacklist, inputs=[file_all_tags_list_blacklist], outputs=[blacklist_group_var])

if __name__ == "__main__":
    # init client & server connection
    HOST = "127.0.0.1"

    demo.queue().launch()