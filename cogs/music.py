import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os


# https://github.com/ytdl-org/youtube-dl/blob/master/README.md#post-processing-options
ytdlp_format_options = {  # sets the quality of the audio
    'format': 'worstaudio',
    'outtmpl': 'zz-%(id)s-%(title)s.%(ext)s',  # z to put it at the most bottom
    'restrictfilenames': True,
    'noplaylist': False,
    'ignoreerrors': False,
    # 'logtostderr': False,
    # 'concurrent_fragment_downloads': 5,
    'max_filesize': 5000000,  # 5MB bytes
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}  # spam of comments to see which is unneeded

ytdl = yt_dlp.YoutubeDL(ytdlp_format_options)  # loading youtube download options


async def getVideoData(searchString: str, download=False):  # throwing search in to get a ton of data
    data = ytdl.extract_info(searchString, download=download)
    entries = data.get('entries')
    if entries is not None:
        return entries[0] if len(entries) > 0 else None
    else:
        return data


class VideoData:  # getting video's youtube title
    def __init__(self, extractedData):
        self.title = extractedData['title']
        self.url = extractedData['webpage_url']
        if self.title is None or self.url is None:
            raise RuntimeError('The extracted data specified does not have one of the following:'
                               'title, webpage_url')


class VideoQueueItem:  # download the video
    def __init__(self, videoData: VideoData):
        self.videoData = videoData

    async def __download(self):
        parseToList = [self.videoData.url]  # convert to list[]
        ytdl.download(parseToList)  # they use a for loop, so the string breaks down into chars

    async def download(self):
        await self.__download()


class VideoQueue:  # a queue for each server
    """the main queue to add and extract data from a dictionary"""

    queue = {}  # set class as dictionary

    def displayQueue(self, server):
        return self.queue[server]

    def addVideo(self, server, videoData):
        if server not in self.queue:  # if the key "server's name" does not exist, create it.
            self.queue[server] = {  # { server_key: {"loop": False, "auto_play_flag": False, "song": ["song_name"]}}
                "loop": False,
                "auto_play_flag": False,
                "song": [videoData]  # <cogs.music.VideoData object at 0x000002446BAD1640> isn't workable with
            }

        else:
            self.queue[server]["song"].append(videoData)
        print(self.queue, "\n")

    async def removeVideo(self, server, videoItem: int):
        del (self.queue[server]["song"][videoItem])


class AutoPlay:
    """handles everything related to playing audio"""

    def __init__(self, server_id):
        self.server_id = server_id
        # self.loop = self.queue["loop"]
        # self.auto_play_flag = self.queue["auto_play_flag"]

    async def play_(self, ctx, data, file_name):
        if type(data) == dict:
            print("you used play")
            print(type(data))  # <cogs.music.VideoData object at 0x00000260AB2B6910> <class 'cogs.music.VideoData'>
            video = VideoData(data)    # hol up, it's object anyways?
            print(video)
            print(type(video))
        else:
            print("you used queue")
            video = data  # <cogs.music.VideoData object at 0x00000260AAB69280>
            print(video)
        current_song = video.title

        queue = VideoQueue()

        server = self.server_id  # the server where the command is sent
        voice_channel = ctx.message.guild.voice_client  # the voice channel of the user who sent the command

        try:  # try to stop current song to play_ new song
            voice_channel.stop()
        except discord.ClientException:
            pass

        async with ctx.typing():
            video = VideoQueueItem(video)  # hol up, it's object anyways?
            await video.download()

            voice_channel.play(discord.FFmpegOpusAudio(file_name))  # play_ song

            try:  # if there's no queue, ignore loop
                loop = queue.displayQueue(server)
                if loop[server]["loop"]:
                    queue.addVideo(server, data)  # adding back into the queue if loop is True
            except KeyError:
                pass

            await ctx.send(f"**Now playing:** {current_song}")

    async def play_next(self, ctx, songObject):
        """check if song is still playing, if not, play_ next and delete file. Try catch for when bot disconnects"""
        # print(songObject)
        print(songObject)
        file_name = ytdl.prepare_filename(songObject)
        await self.play_(ctx, songObject, file_name)
        await self.delete_audio_file(ctx, file_name)
        queue = VideoQueue().displayQueue(ctx.message.guild.id)
        flag = queue["auto_play_flag"]
        print(flag)

        while flag:
            while ctx.message.guild.voice_client.is_playing():
                await asyncio.sleep(2)
                print("play_")
                pass
            print("plong")
            del(queue["song"][0])  # song's played, so, YEET
            if queue["song"][0]:
                print("AUTOPLAY WOOOO")
                song_data = await getVideoData(queue["song"][0])
                file_name = ytdl.prepare_filename(song_data)
                await self.play_(ctx, song_data, file_name)  # play_ next song on list
            else:
                print(False)
                queue["auto_play_flag"] = False

    @staticmethod
    async def delete_audio_file(ctx, file_name):
        """deletes song at the end of the song"""
        while True:
            try:
                while ctx.message.guild.voice_client.is_playing():
                    await asyncio.sleep(2)
                    pass
                await asyncio.sleep(2)
                os.remove(file_name)
                print(file_name)
                break
            except AttributeError:
                await asyncio.sleep(2)
                os.remove(file_name)
                print(file_name)


class Music(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Music is loaded")

    # commands starts here
    @commands.command(name="loop")
    async def loop_(self, ctx):

        try:
            server = ctx.message.guild
            loop = VideoQueue().displayQueue(ctx.message.guild)

            if loop[0]:  # index 0 for loop boolean
                await ctx.send("Loop mode is now disabled")
                VideoQueue().queue[server]["loop"] = False

            else:
                await ctx.send("Loop mode is now enabled")
                VideoQueue().queue[server]["loop"] = True
        except KeyError:
            await ctx.send("You do not have a queue in the server")

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, title):

        if not ctx.message.author.voice:
            await ctx.send("You are not connected to a voice channel")
            return
        else:
            channel = ctx.message.author.voice.channel

        try:  # if bot is not in VC, join it
            await channel.connect()
        except discord.ClientException:
            pass

        server = ctx.message.guild.id
        queue = VideoQueue()
        data = await getVideoData(title)  # getting all of the data beforehand, song title, id, etc

        if title.lower() == "queue" or title.lower() == "q":
            data = queue.displayQueue(server)
            data["auto_play_flag"] = True
            song_title = data["song"][0]
            song_data = await getVideoData(song_title)
            # print(song_data)
            await AutoPlay(server).play_next(ctx, song_data)
            return

        try:
            # print(data)
            await AutoPlay(server).play_next(ctx, data)
        except FileNotFoundError:
            await ctx.send("file's too big ya cunt")
        except KeyError:
            pass  # if there's no queue, this will be triggered

        try:
            if queue.displayQueue(server):  # if queue exists, enable auto play_
                queue.queue[server]["auto_play_flag"] = True
        except KeyError:
            pass

        await AutoPlay.delete_audio_file(ctx, ytdl.prepare_filename(data))

    @commands.command(aliases=["stop"])
    async def pause(self, ctx):
        server = ctx.message.guild
        voice_channel = server.voice_client

        voice_channel.pause()

    @commands.command()
    async def resume(self, ctx):
        server = ctx.message.guild
        voice_channel = server.voice_client

        voice_channel.resume()

    @commands.command(aliases=['s'])
    async def skip(self, ctx):
        voice_channel = ctx.message.guild.voice_client

        try:
            voice_channel.stop()

            # async with ctx.typing():
            #   call AutoPlay
            # await ctx.send(f"**Now playing:** {ctx}")
            await ctx.send("Feature not implemented, ping my creator")
        except discord.VoiceClient:
            await ctx.send("There is no song to skip")

    @commands.command
    async def shuffle(self, ctx):
        raise NotImplementedError

    @commands.command(name="queue", aliases=['q'])
    async def queue_(self, ctx, *, search):

        song_data = VideoData(await getVideoData(search))
        server = ctx.message.guild.id
        print(song_data)
        VideoQueue().addVideo(server, song_data.title)

        await ctx.send(f"`{song_data.title}` added to queue")

    @queue_.error
    async def queue_error(self, ctx, error):
        await ctx.send("You need to include the song that you want to queue `!queue song`")
        print(error)

    @commands.command(aliases=['r'])
    async def remove(self, ctx, songIndex):
        server = ctx.message.guild.id
        songIndex = int(songIndex) - 1  # -1 cuz index starts at 0

        await VideoQueue().removeVideo(server, songIndex)
        queue = VideoQueue().displayQueue(server)  # retrieving queue from class

        # TODO: prepare embed here

        await ctx.send(f"Your queue is now `{queue}`")

    @remove.error
    async def remove_error(self, ctx, error):  # even if unused, error variable is received
        await ctx.send(f"{ctx.author.mention} Your queue is empty or you gave a invalid number")
        print(error)

    @commands.command(aliases=['v', "list"])
    async def view(self, ctx):
        try:
            server = ctx.message.guild.id
            queue_ = VideoQueue().displayQueue(server)["song"]
            queue = ''
            num = 0
            for x in queue_:
                num += 1
                title = x
                queue = queue + str(num) + ". " + title + "\n"  # 1. song_title\n
            await ctx.send(f"`{queue}`")
            print("done")
        except KeyError:
            await ctx.send("The queue is empty")

    @commands.command(aliases=['l'])
    async def leave(self, ctx):
        # queue obj
        # queue = []  # erase queue on leave
        voice_client = ctx.message.guild.voice_client
        await voice_client.disconnect()
        await ctx.send("Bye!")

    @leave.error
    async def leave_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send("But I'm not in a voice channel?")

    # autoplay feature here probably


def setup(bot):
    bot.add_cog(Music(bot))
